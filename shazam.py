import numpy as np
import scipy.ndimage
import matplotlib.mlab as mlab
import librosa
import sqlite3
import hashlib
from typing import List, Tuple, Any, Dict # For type hinting

# --- Configuration Constants ---
NFFT_VAL = 4096
NOVERLAP_VAL = 2048  # Typically NFFT / 2
PEAK_NEIGHBORHOOD_SIZE_VAL = 20 # Size of the neighborhood for peak picking
HASH_FAN_VALUE_VAL = 15 # Number of peaks to pair with for hashing
HASH_TIME_WINDOW_VAL = 200 # Max time difference (frames) between peaks for hashing
DB_NAME_VAL = 'fingerprints.db'

# --- Database Functions ---

def init_db(db_name: str = DB_NAME_VAL) -> sqlite3.Connection:
    """
    Initializes the SQLite database and creates the required tables if they do not exist.

    Args:
        db_name (str): Name of the SQLite database file.

    Returns:
        sqlite3.Connection: A connection object to the SQLite database.
    """
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    # Create 'songs' table to store song metadata
    c.execute('''
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE 
        )
    ''') 
    # Create 'fingerprints' table to store fingerprint hashes associated with songs
    c.execute('''
        CREATE TABLE IF NOT EXISTS fingerprints (
            hash TEXT,
            song_id INTEGER,
            offset INTEGER,
            PRIMARY KEY (hash, song_id, offset), 
            FOREIGN KEY(song_id) REFERENCES songs(id)
        )
    ''') 
    conn.commit()
    return conn

def store_fingerprints(conn: sqlite3.Connection, song_name: str, hashes: List[Tuple[str, int]]):
    """
    Stores the song and its fingerprints in the database.

    Args:
        conn (sqlite3.Connection): Database connection object.
        song_name (str): Name of the song.
        hashes (list): List of tuples containing hash values and offsets.
    """
    c = conn.cursor()
    try:
        # Check if song already exists
        c.execute("SELECT id FROM songs WHERE name = ?", (song_name,))
        song_row = c.fetchone()
        if song_row:
            print(f"Song '{song_name}' already exists in the database (ID: {song_row[0]}). Fingerprints will be added if new.")
            song_id = song_row[0]
        else:
            c.execute("INSERT INTO songs (name) VALUES (?)", (song_name,))
            song_id = c.lastrowid
            if song_id is None: 
                 raise sqlite3.Error("Failed to get last row ID after inserting song.")

        
        fingerprints_to_insert = []
        for hash_val, offset in hashes:
            fingerprints_to_insert.append((hash_val, song_id, int(offset)))

        if fingerprints_to_insert:
            c.executemany("INSERT OR IGNORE INTO fingerprints (hash, song_id, offset) VALUES (?, ?, ?)",
                          fingerprints_to_insert)
        conn.commit()
    except sqlite3.IntegrityError as ie:
        print(f"Integrity error while storing fingerprints for '{song_name}': {ie}.")
        conn.rollback() 
    except Exception as e:
        print(f"An error occurred while storing fingerprints for '{song_name}': {e}")
        conn.rollback()


# --- Fingerprinting Functions ---

def generate_fingerprints(
    audio_path: str, 
    nfft: int = NFFT_VAL, 
    noverlap: int = NOVERLAP_VAL,
    peak_neighborhood_size: int = PEAK_NEIGHBORHOOD_SIZE_VAL,
    hash_fan_value: int = HASH_FAN_VALUE_VAL,
    hash_time_window: int = HASH_TIME_WINDOW_VAL
) -> List[Tuple[str, int]]:
    """
    Generates audio fingerprints from an audio file.
    Returns an empty list if an error occurs or no fingerprints can be generated.
    """
    try:
        y, sr = librosa.load(audio_path, mono=True)
        if y is None or len(y) == 0:
            print(f"Warning: Audio file {audio_path} loaded as empty or None. Cannot generate fingerprints.")
            return []
    except FileNotFoundError:
        print(f"Error: Audio file not found at {audio_path}")
        return []
    except Exception as e: 
        print(f"Error loading audio file {audio_path}: {e}")
        return []

    try:
        spectrogram, _, _ = mlab.specgram(y, NFFT=nfft, Fs=sr, noverlap=noverlap)

        if spectrogram is None or spectrogram.size == 0:
            print(f"Warning: Spectrogram for {audio_path} is empty. Cannot generate fingerprints.")
            return []

        epsilon = 1e-10 
        log_spectrogram = 10 * np.log10(spectrogram + epsilon)

        peaks = get_peaks(log_spectrogram, peak_neighborhood_size)
        if peaks.size == 0: # Check if peaks array is empty
            print(f"Warning: No peaks found in {audio_path}. Cannot generate fingerprints.")
            return []
            
        hashes = generate_hashes(peaks, fan_value=hash_fan_value, time_window=hash_time_window)
        return hashes
    except Exception as e:
        print(f"Error generating fingerprints for {audio_path}: {e}")
        return []


def get_peaks(spectrogram: np.ndarray, neighborhood_size: int) -> np.ndarray:
    """
    Identifies peaks in the spectrogram.
    Returns an empty ndarray if spectrogram is empty or no peaks are found.
    """
    if spectrogram is None or spectrogram.size == 0:
        return np.array([])

    struct = scipy.ndimage.generate_binary_structure(2, 1)
    neighborhood = scipy.ndimage.iterate_structure(struct, neighborhood_size)

    local_max = scipy.ndimage.maximum_filter(spectrogram, footprint=neighborhood) == spectrogram
    
    background = (spectrogram == np.min(spectrogram)) 
    eroded_background = scipy.ndimage.binary_erosion(background, structure=neighborhood, border_value=1)
    
    detected_peaks = local_max ^ eroded_background
    
    peaks = np.argwhere(detected_peaks) 
    return peaks


def generate_hashes(peaks: np.ndarray, fan_value: int, time_window: int) -> List[Tuple[str, int]]:
    """
    Generates hash values from the identified peaks by pairing them.
    """
    hashes: List[Tuple[str, int]] = []
        
    # Ensure peaks is a 2D array with shape (num_peaks, 2) and has at least 2 peaks for pairing.
    if not isinstance(peaks, np.ndarray) or peaks.ndim != 2 or peaks.shape[1] != 2 or peaks.shape[0] < 2:
        return hashes

    # Sort by time (peaks[:,1]), then by frequency (peaks[:,0]) for consistent pairing
    peaks_sorted = peaks[np.lexsort((peaks[:, 0], peaks[:, 1]))]

    for i in range(len(peaks_sorted)):
        anchor_peak_time = int(peaks_sorted[i][1])
        anchor_peak_freq = int(peaks_sorted[i][0])
        
        for j in range(i + 1, min(i + 1 + fan_value, len(peaks_sorted))):
            target_peak_time = int(peaks_sorted[j][1])
            target_peak_freq = int(peaks_sorted[j][0])
            
            time_diff = target_peak_time - anchor_peak_time
            
            if 0 < time_diff <= time_window:
                hash_input = f"{anchor_peak_freq}|{target_peak_freq}|{time_diff}"
                hash_output = hashlib.sha1(hash_input.encode('utf-8')).hexdigest()
                hashes.append((hash_output, anchor_peak_time))
            elif time_diff > time_window: 
                break 
    return hashes

# --- Recognition Function ---

def recognize_audio(conn: sqlite3.Connection, audio_path: str) -> None:
    """
    Recognizes an audio sample by matching its fingerprints against the database.
    """
    print(f"Attempting to recognize '{audio_path}'...")
    sample_hashes = generate_fingerprints(
        audio_path,
        nfft=NFFT_VAL,
        noverlap=NOVERLAP_VAL,
        peak_neighborhood_size=PEAK_NEIGHBORHOOD_SIZE_VAL,
        hash_fan_value=HASH_FAN_VALUE_VAL,
        hash_time_window=HASH_TIME_WINDOW_VAL
    )

    if not sample_hashes:
        print("Could not generate fingerprints for the sample. (Is the file a valid audio file, long enough, and contains distinct features?)")
        return

    c = conn.cursor()
    
    query_hashes_list = [h[0] for h in sample_hashes]

    placeholders = ','.join(['?'] * len(query_hashes_list))
    sql = f"SELECT hash, song_id, offset FROM fingerprints WHERE hash IN ({placeholders})"
    
    try:
        c.execute(sql, query_hashes_list)
        db_matches = c.fetchall()
    except sqlite3.Error as e:
        print(f"Database error during recognition query: {e}")
        return

    if not db_matches:
        print("No fingerprints from this sample were found in the database.")
        return

    sample_hash_map: Dict[str, List[int]] = {}
    for h_val, h_offset in sample_hashes:
        h_offset_int = int(h_offset)
        if h_val not in sample_hash_map:
            sample_hash_map[h_val] = []
        sample_hash_map[h_val].append(h_offset_int)

    match_counts: Dict[Tuple[int, int], int] = {}

    for db_hash, song_id, db_offset_val in db_matches:
        db_offset = int(db_offset_val)
        if db_hash in sample_hash_map:
            for sample_offset in sample_hash_map[db_hash]:
                time_difference = db_offset - sample_offset
                key = (song_id, time_difference)
                match_counts[key] = match_counts.get(key, 0) + 1
            
    if not match_counts:
        print("No consistent song matches found after time alignment (unexpected).")
        return

    best_match_key, best_match_count = max(match_counts.items(), key=lambda item: item[1])
    
    matched_song_id = best_match_key[0]

    c.execute("SELECT name FROM songs WHERE id = ?", (matched_song_id,))
    song_name_tuple = c.fetchone()

    if song_name_tuple:
        print(f"--- Best match: '{song_name_tuple[0]}' (Confidence score: {best_match_count}) ---")
    else:
        print(f"Error: Could not find song name for recognized ID: {matched_song_id}. Database might be inconsistent.")


# --- Main Application Logic ---

def main():
    """
    Main function to run the audio fingerprinting system.
    Provides a command-line interface for the user to interact with.
    """
    conn = None 
    try:
        conn = init_db() 
        while True:
            print("\nAudio Fingerprinting System")
            print("-----------------------------")
            print("1. Add a song to the database")
            print("2. Recognize an audio sample")
            print("3. Exit")
            choice = input("Enter your choice (1-3): ").strip()

            if choice == '1':
                song_path = input("Enter the path to the song file (e.g., /path/to/song.mp3): ").strip()
                song_name = input("Enter the song name: ").strip()
                if not song_path or not song_name:
                    print("Error: Song path and name cannot be empty.")
                    continue
                try:
                    print(f"Processing '{song_name}' from '{song_path}'...")
                    hashes = generate_fingerprints(
                        song_path,
                        nfft=NFFT_VAL,
                        noverlap=NOVERLAP_VAL,
                        peak_neighborhood_size=PEAK_NEIGHBORHOOD_SIZE_VAL,
                        hash_fan_value=HASH_FAN_VALUE_VAL,
                        hash_time_window=HASH_TIME_WINDOW_VAL
                    )
                    if hashes:
                        store_fingerprints(conn, song_name, hashes)
                        print(f"Song '{song_name}' and its fingerprints have been processed.")
                    else:
                        print(f"Could not generate fingerprints for '{song_name}'. Song not added. (Is it a valid audio file, long enough, with distinct features?)")
                except Exception as e: 
                    print(f"An unexpected error occurred while adding song '{song_name}': {e}")

            elif choice == '2':
                sample_path = input("Enter the path to the audio sample for recognition: ").strip()
                if not sample_path:
                    print("Error: Sample path cannot be empty.")
                    continue
                try:
                    recognize_audio(conn, sample_path)
                except Exception as e: 
                    print(f"An unexpected error occurred during recognition of '{sample_path}': {e}")

            elif choice == '3':
                print("Exiting application.")
                break
            else:
                print("Invalid choice. Please enter a number between 1 and 3.")
    except sqlite3.Error as e:
        print(f"A critical database error occurred: {e}. Please check the database file '{DB_NAME_VAL}'.")
    except Exception as e:
        print(f"An unexpected critical error occurred in the application: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    main()