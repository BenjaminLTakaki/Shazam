import numpy as np 
import scipy.ndimage 
import matplotlib.mlab as mlab 
import librosa 
import sqlite3 
import hashlib 

def init_db(db_name='fingerprints.db'):
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
            name TEXT
        )
    ''')
    # Create 'fingerprints' table to store fingerprint hashes associated with songs
    c.execute('''
        CREATE TABLE IF NOT EXISTS fingerprints (
            hash TEXT,
            song_id INTEGER,
            offset INTEGER,
            FOREIGN KEY(song_id) REFERENCES songs(id)
        )
    ''')
    conn.commit()
    return conn

def generate_fingerprints(audio_path):
    """
    Generates audio fingerprints from an audio file.

    Args:
        audio_path (str): Path to the audio file.

    Returns:
        list: A list of tuples containing hash values and their corresponding offsets.
    """
    y, sr = librosa.load(audio_path, mono=True)
    spectrogram, freqs, times = mlab.specgram(y, NFFT=4096, Fs=sr, noverlap=2048)
    log_spectrogram = 10 * np.log10(spectrogram)
    peaks = get_peaks(log_spectrogram)
    hashes = generate_hashes(peaks)
    return hashes

def get_peaks(spectrogram):
    """
    Identifies peaks in the spectrogram.

    Args:
        spectrogram (ndarray): The logarithmic spectrogram array.

    Returns:
        ndarray: An array of peak indices.
    """
    struct = scipy.ndimage.generate_binary_structure(2, 1)
    neighborhood = scipy.ndimage.iterate_structure(struct, 20)
    local_max = scipy.ndimage.maximum_filter(spectrogram, footprint=neighborhood) == spectrogram
    background = (spectrogram == 0)
    eroded_background = scipy.ndimage.binary_erosion(background, structure=neighborhood, border_value=1)
    detected_peaks = local_max ^ eroded_background
    peaks = np.argwhere(detected_peaks)
    return peaks

def generate_hashes(peaks, fan_value=15):
    """
    Generates hash values from the identified peaks.

    Args:
        peaks (ndarray): An array of peak indices.
        fan_value (int): Number of neighboring peaks to consider for hashing.

    Returns:
        list: A list of tuples containing hash values and their corresponding offsets.
    """
    hashes = []
    peaks = sorted(peaks, key=lambda x: x[1])
    for i in range(len(peaks)):
        for j in range(1, fan_value):
            if (i + j) < len(peaks):
                freq1 = int(peaks[i][0])  
                freq2 = int(peaks[i + j][0])  
                t1 = int(peaks[i][1])  
                t2 = int(peaks[i + j][1])   
                time_diff = t2 - t1
                if time_diff > 0 and time_diff <= 200:
                    hash_input = f"{freq1}|{freq2}|{time_diff}"
                    hash_output = hashlib.sha1(hash_input.encode('utf-8')).hexdigest()
                    hashes.append((hash_output, t1))
    return hashes

def store_fingerprints(conn, song_name, hashes):
    """
    Stores the song and its fingerprints in the database.

    Args:
        conn (sqlite3.Connection): Database connection object.
        song_name (str): Name of the song.
        hashes (list): List of tuples containing hash values and offsets.
    """
    c = conn.cursor()
    c.execute("INSERT INTO songs (name) VALUES (?)", (song_name,))
    song_id = c.lastrowid
    for hash_val, offset in hashes:
        offset = int(offset) 
        c.execute("INSERT INTO fingerprints (hash, song_id, offset) VALUES (?, ?, ?)",
                  (hash_val, song_id, offset))
    conn.commit()

def recognize_audio(conn, audio_path):
    """
    Recognizes an audio sample by matching its fingerprints against the database.

    Args:
        conn (sqlite3.Connection): Database connection object.
        audio_path (str): Path to the audio sample.
    """

    sample_hashes = generate_fingerprints(audio_path)
    c = conn.cursor()
    hash_dict = {}
    for hash_val, offset in sample_hashes:
        offset = int(offset) 
        c.execute("SELECT song_id, offset FROM fingerprints WHERE hash = ?", (hash_val,))
        results = c.fetchall()
        for song_id, db_offset in results:
            db_offset = int(db_offset) 
            time_diff = db_offset - offset
            key = (song_id, time_diff)
            hash_dict[key] = hash_dict.get(key, 0) + 1
    if hash_dict:
        best_match = max(hash_dict.items(), key=lambda x: x[1])
        song_id = best_match[0][0]
        c.execute("SELECT name FROM songs WHERE id = ?", (song_id,))
        song_name = c.fetchone()[0]
        print(f"Best match: {song_name}")
    else:
        print("No match found.")

def main():
    """
    Main function to run the audio fingerprinting system.
    Provides a command-line interface for the user to interact with.
    """
    conn = init_db()
    while True:
        print("\nOptions:")
        print("1. Add a song to the database")
        print("2. Recognize an audio sample")
        print("3. Exit")
        choice = input("Enter your choice: ")
        if choice == '1':
            song_path = input("Enter the path to the song file: ")
            song_name = input("Enter the song name: ")
            # Generate fingerprints and store them in the database
            hashes = generate_fingerprints(song_path)
            store_fingerprints(conn, song_name, hashes)
            print(f"Added {song_name} to the database.")
        elif choice == '2':
            sample_path = input("Enter the path to the audio sample: ")
            # Recognize the audio sample
            recognize_audio(conn, sample_path)
        elif choice == '3':
            # Close the database connection and exit
            conn.close()
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == '__main__':
    main()
