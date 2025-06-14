# Audio Fingerprinting System (Shazam Clone)

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Usage](#usage)
6. [Configuration](#configuration)
7. [Contributing](#contributing)
8. [License](#license)

---

## Overview

A command-line audio fingerprinting tool inspired by Shazam. It analyzes audio files to generate compact, robust fingerprints, stores them in a local SQLite database, and recognizes unknown samples by matching fingerprint hashes.

## Features

* **Robust Fingerprinting**: Uses STFT and peak picking to extract stable audio landmarks
* **Efficient Hashing**: Combines frequency and time-difference pairs hashed with SHA-1
* **Local Storage**: SQLite database for quick insertions and lookups
* **High Accuracy**: Matches based on consistent time-offset alignments
* **Easy CLI**: Simple menu-driven interface, no web server required

## Architecture

```mermaid
flowchart LR
  A[Load Audio] --> B[Compute Spectrogram (STFT)]
  B --> C[Log-Scale & Peak Picking]
  C --> D[Generate Hashes]
  D --> E[Database: Store/Query]
  E --> F[Recognition & Results]
```

---

## Installation

Ensure you have Python 3.7+ installed, then:

```bash
pip install numpy scipy matplotlib librosa
```

---

## Usage

Run the main script to launch the CLI:

```bash
python shazam.py
```

Follow the prompts:

1. **Add a song**: Provide an audio file path and a name
2. **Recognize a sample**: Provide a sample file path to identify
3. **Exit**

### Example

```bash
# Add "MySong.mp3" to the database
> python shazam.py
> 1
> /path/to/MySong.mp3
> My Song

# Recognize a 5s sample
> python shazam.py
> 2
> /path/to/sample.wav
```

---

## Configuration Parameters

| Parameter                    | Default | Description                                           |
| ---------------------------- | ------- | ----------------------------------------------------- |
| `NFFT_VAL`                   | `4096`  | FFT window size (frequency resolution)                |
| `NOVERLAP_VAL`               | `2048`  | Overlap between consecutive windows                   |
| `PEAK_NEIGHBORHOOD_SIZE_VAL` | `20`    | Neighborhood radius for peak detection                |
| `HASH_FAN_VALUE_VAL`         | `15`    | Number of peak pairs (fan-out) per anchor peak        |
| `HASH_TIME_WINDOW_VAL`       | `200`   | Maximum frame-difference allowed between paired peaks |

---

## Contributing

Contributions are welcome! Please fork the repo, make your changes, and open a pull request with a clear description of your improvements.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
