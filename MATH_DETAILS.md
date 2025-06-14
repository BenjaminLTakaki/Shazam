# Mathematical Details of Audio Fingerprinting

This document provides a clear, visual breakdown of the core algorithms and mathematical concepts behind the audio fingerprinting system.

---

## 1. Spectrogram Generation (STFT)

The Short-Time Fourier Transform (STFT) converts the time-domain signal into a time–frequency representation:

$\displaystyle X[n, k] = \sum_{m=0}^{N-1} x[n + m] \, w[m] \, e^{-j2\pi k m / N} $

* **Parameters:**

  * $N = NFFT\_VAL$: window size
  * $w[m]$: window function (e.g., Hamming)
  * $x[n]$: audio signal samples
  * $k$: frequency bin index

After computing \\(X\[n, k]\\), we convert power to decibels:

$\displaystyle S[n, k] = 10 \cdot \log_{10}\bigl(|X[n, k]|^2 + \varepsilon\bigr) $

where $\varepsilon$ prevents $\log(0)$.

---

## 2. Peak Picking

Identify local maxima in the log-spectrogram $S[n,k]$:

1. **Neighborhood Definition**: size $P = \text{PEAK\_NEIGHBORHOOD\_SIZE\_VAL}$
2. **Local Maximum Filter**: $S[n,k] = \max_{(i,j)\in \mathcal{N}_P(n,k)} S[i,j]$
3. **Background Erosion**: remove flat/min regions to reduce noise peaks

<aside>
⚙️ A point \((n,k)\) is a peak if it equals the max in its neighborhood and is above the eroded background.
</aside>

---

## 3. Fingerprint Hashing

Construct pairs of peaks to form robust landmarks:

1. **Anchor Peak**: $(f_i, t_i)$
2. **Target Peaks**: next $F = \text{HASH\_FAN\_VALUE\_VAL}$ peaks within $\Delta T_{\max} = \text{HASH\_TIME\_WINDOW\_VAL}$
3. **Compute Differences:**

   * Frequency difference: $\Delta f = f_j - f_i$
   * Time difference: $\Delta t = t_j - t_i$
4. **Hash Input:**

   ```text
   freq1|freq2|delta_t
   ```
5. **SHA-1 Hash:**
   $h = \mathrm{SHA1}('freq1|freq2|delta_t')$

Each hash is stored alongside the anchor time $t_i$.

---

## Workflow Overview

```mermaid
flowchart LR
  A[Load & Preprocess Audio] --> B[STFT & Log-Scale]
  B --> C[Peak Picking]
  C --> D[Pair Peaks]
  D --> E[Compute SHA-1 Hashes]
  E --> F[Store/Query DB]
```

---

## 4. Parameter Trade-offs

| Parameter                         | Effect of Increase                     | Effect of Decrease                     |
| --------------------------------- | -------------------------------------- | -------------------------------------- |
| **NFFT\_VAL**                     | ↑ Frequency resolution, ↑ compute time | ↓ Detail, ↑ speed                      |
| **NOVERLAP\_VAL**                 | ↓ Spectral leakage, ↑ frame count      | ↑ artifacts, ↓ data volume             |
| **PEAK\_NEIGHBORHOOD\_SIZE\_VAL** | ↑ robustness (fewer peaks)             | ↑ sensitivity (more peaks, more noise) |
| **HASH\_FAN\_VALUE\_VAL**         | ↑ matching robustness, ↑ hash volume   | ↓ match candidates, ↑ false negatives  |
| **HASH\_TIME\_WINDOW\_VAL**       | ↑ pairing range (longer time context)  | ↓ temporal context (shorter window)    |

---

### Robustness Considerations

* Noise and minor distortions: Handled by log-scaling and local maxima filtering.
* Compression artifacts: Tolerated within peak-picking noise threshold.
* Speed/pitch variations: Significant shifts may reduce match accuracy.

---

---

## 5. Terminology Explained

* **Short-Time Fourier Transform (STFT):** A process that slices the signal into short, overlapping frames (windows) and applies the Fourier transform to each frame, capturing how frequency content evolves over time.
* **Window Function (e.g., Hamming):** A weighting function applied to each frame to taper its edges, reducing spectral leakage (unwanted spread of frequency components).
* **Decibel (dB) Scale:** A logarithmic unit measuring power ratios: 10·log₁₀(power). Converts large dynamic ranges into manageable values and emphasizes quieter signals.
* **Neighborhood (for Peak Picking):** A local region in time–frequency space of radius P, used to determine if a point is a local maximum by comparing it to its immediate surroundings.
* **Background Erosion:** A morphological operation that shrinks regions of low-intensity values, isolating peaks by removing flat or noisy areas in the spectrogram.
* **Fan-Out (HASH\_FAN\_VALUE\_VAL):** Number of target peaks paired with each anchor peak; controls how many hash points each anchor generates for matching.
* **SHA-1 Hash:** A 160-bit cryptographic hash function that produces a fixed-length fingerprint from variable-length input, enabling efficient comparisons and database indexing.
* **Time–Frequency Landmark:** A pair of peaks (anchor + target) defined by their (frequency, time) coordinates; forms the basic unit for fingerprint hashing.

---

*End of Mathematical Details.*
