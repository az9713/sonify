# The Science of Sonify

## Sonification Theory and Physical Modeling

---

## 1. Introduction: Sonification as Scientific Method

Sonification --- the systematic mapping of data to non-speech audio --- is not ornamentation.
It is a perceptual channel with distinct advantages over visualization for certain classes
of data. The human auditory system resolves temporal patterns down to ~2 ms (compared to
~25 ms for vision), detects anomalies in ongoing streams without focused attention
(the "cocktail party effect"), and processes multiple layered signals simultaneously
(we hear melody, harmony, rhythm, and timbre in parallel).

Sonify implements **parameter-mapping sonification** (PMSon), the most
widely studied sonification paradigm. In PMSon, each data dimension is mapped to a
distinct auditory dimension through a transfer function. The critical constraint is that
these mappings must be:

1. **Monotone** --- higher input always yields higher output (or always lower). This
   makes the mapping learnable; a listener can internalize the relationship after brief
   exposure.

2. **Continuous** --- small data changes produce small audio changes. Discontinuities
   are reserved for genuine discontinuities in the data (e.g., arrhythmia events,
   network bursts).

3. **Deterministic** --- the same data always produces the same sound. The audio
   engine (Lyria, ElevenLabs, or the mock synthesizer) is downstream of the mapping;
   it receives control parameters but never decides what those parameters mean.

The mathematical pipeline for every lens is:

```
x(t)  --->  f: R^n -> R^m  --->  EMA_alpha  --->  clamp  --->  audio engine
data        lens.map()          smoothing       valid ranges    Lyria / ElevenLabs / mock
```

where `x(t)` is the domain state vector at time `t`, `f` is the deterministic transfer
function implemented by each lens's `map()` method, `EMA_alpha` is exponential moving
average smoothing (Section 2), and `clamp` restricts outputs to Lyria's valid parameter
ranges.

---

## 2. Signal Processing: Temporal Smoothing and Control Stability

### 2.1 The Exponential Moving Average as a Causal Low-Pass Filter

Raw data-to-audio mapping produces perceptually jarring results. A temperature reading
that jumps from 20.1 to 20.3 C between ticks would cause an audible brightness flicker.
We need a **causal low-pass filter** --- one that uses only past and present values
(no lookahead).

The exponential moving average (EMA) is the simplest such filter:

```
y[n] = alpha * x[n] + (1 - alpha) * y[n-1]
```

where `alpha in (0, 1]` is the smoothing factor. This is a first-order IIR
(Infinite Impulse Response) filter with transfer function:

```
H(z) = alpha / (1 - (1 - alpha) * z^{-1})
```

The **cutoff frequency** (the -3 dB point) of this filter in continuous-time terms is:

```
f_c = -ln(1 - alpha) / (2 * pi * T)
```

where `T` is the sampling interval (1/tick_hz). With our default `alpha = 0.15` and a
typical tick rate of 5 Hz:

```
f_c = -ln(0.85) / (2 * pi * 0.2) = 0.1625 / 1.257 = 0.129 Hz
```

This means changes faster than ~0.13 Hz (period > ~7.7 seconds) pass through with less
than 3 dB attenuation, while faster fluctuations are progressively damped. This matches
the perceptual time constant for musical parameter changes --- listeners can track
gradual evolution over several seconds but are disturbed by sub-second jumps in tempo
or timbre.

**Implementation** (`lenses/base.py:91-99`):

```python
def _ema(self, key: str, value: float) -> float:
    if key not in self._ema_state:
        self._ema_state[key] = value
    else:
        self._ema_state[key] = (
            self._ema_alpha * value + (1 - self._ema_alpha) * self._ema_state[key]
        )
    return self._ema_state[key]
```

Each control dimension (`bpm`, `density`, `brightness`) maintains independent EMA state.
The first sample initializes the filter (no ramp-up transient).

### 2.2 Control Diffing: Minimizing API Perturbation

The Lyria RealTime API accepts continuous parameter updates, but each update triggers
internal model re-conditioning. Unnecessary updates (sending BPM=120 when BPM is already
120) waste bandwidth and may cause micro-glitches in the audio output.

The `ControlState.diff()` method (`lenses/base.py:40-61`) implements dead-zone
comparison: a parameter is considered "changed" only if it differs from the previous
value by more than a threshold (0.01 for continuous parameters, exact equality for
discrete parameters like `bpm` and `scale`). This is equivalent to a Schmitt trigger
on each control channel, preventing limit-cycle oscillation when a value hovers near
a rounding boundary.

---

## 3. Atmosphere Lens: Meteorological Sonification

### 3.1 Physical Model

The atmosphere lens maps five meteorological variables to musical parameters. Each
mapping has a physical justification rooted in how the variable affects the perceptual
"energy" of weather.

**Wind Speed to BPM (Tempo)**

Wind speed is the kinetic energy density of the atmosphere. The kinetic energy per
unit volume of moving air is:

```
E_k = (1/2) * rho * v^2
```

where `rho ~ 1.225 kg/m^3` at sea level and `v` is wind speed in m/s. The Beaufort
scale --- the standard meteorological classification --- maps wind speed to qualitative
descriptions that follow a clear energy progression:

| Beaufort | v (m/s) | Description     | Musical Analogy     |
|----------|---------|-----------------|---------------------|
| 0-1      | 0-1.5   | Calm            | Largo (40-60 bpm)   |
| 3-4      | 3.4-7.9 | Gentle breeze   | Andante (76-108)    |
| 6-7      | 10.8-17 | Strong breeze   | Allegro (120-156)   |
| 9-10     | 20.8-28 | Storm           | Presto (168-200)    |

Our transfer function linearizes this relationship:

```
BPM = 70 + v * 3.67
```

This maps 0 m/s to 70 BPM (largo) and 30 m/s to ~180 BPM (presto), spanning the full
Lyria tempo range. The linear mapping is chosen because the Beaufort scale is itself
approximately linear in the moderate range (Beaufort numbers 2-8), which corresponds to
the most commonly experienced conditions.

**Implementation** (`lenses/atmosphere.py:50`):

```python
bpm = int(self._ema("bpm", 70 + wind * 3.67))
```

**Temperature to Brightness (Timbral Warmth)**

The perceptual correlation between temperature and timbral brightness is well-established
in psychoacoustic literature. "Warm" sounds are described as having attenuated high
frequencies (mellow, dark timbre), while "bright" sounds have strong upper harmonics.
This is not mere metaphor --- functional MRI studies show that thermal and timbral warmth
activate overlapping cortical regions (Occelli et al., 2014).

We map temperature to brightness using a linear normalization over the range
[-10 C, 40 C]:

```
brightness = (T + 10) / 50
```

This yields brightness = 0.0 at -10 C (dark, muffled tone) and brightness = 1.0 at
40 C (sharp, brilliant tone). The domain is chosen to cover the vast majority of
inhabited-earth surface temperatures.

**Implementation** (`lenses/atmosphere.py:53`):

```python
brightness = self._ema("brightness", (temp + 10) / 50)
```

**Humidity to Density (Textural Complexity)**

Humidity measures the mass of water vapor per unit volume of air. High humidity produces
a physically denser atmosphere --- sound propagates differently (speed of sound increases
slightly in humid air due to the lower molecular weight of H2O vs N2/O2). More
importantly, humidity is a proxy for atmospheric complexity: humid air holds more energy
for convective processes, produces clouds, supports precipitation.

We map humidity directly to musical density:

```
density = H / 100
```

where `H` is relative humidity in percent. At density = 0 (dry desert air), the music
is sparse --- few simultaneous voices, minimal accompaniment. At density = 1 (saturated
air), the texture is thick with layered instruments, pads, and harmonic fill.

**Implementation** (`lenses/atmosphere.py:56`):

```python
density = self._ema("density", humidity / 100)
```

**Rain Probability to Musical Mode (Prompt Injection)**

Precipitation fundamentally changes the acoustic character of an outdoor environment.
Rain introduces stochastic percussive energy (individual drop impacts are a Poisson
process with rate proportional to rainfall intensity). We model this by injecting
piano arpeggio prompts when rain probability exceeds 0.3:

```python
if rain > 0.3:
    prompts.append({"text": "Piano arpeggios, rain, gentle", "weight": rain})
```

The prompt weight scales with rain probability, so light rain produces gentle arpeggios
(weight ~0.3-0.5) while heavy rain drives them to full prominence (weight ~0.8-1.0).
The choice of arpeggios is deliberate --- their rapid, discrete note attacks mirror the
stochastic texture of rainfall.

**Storm Detection: Compound Condition**

Storms are not merely high wind or heavy rain in isolation --- they are the co-occurrence
of both. We model this as a logical conjunction:

```python
if wind > 20 and rain > 0.5:
    prompts.append({"text": "Dirty synths, crunchy distortion, ominous drone", "weight": 0.8})
```

This injects distorted timbres only when both conditions are met, mimicking how a storm's
acoustic character (low-frequency rumble, broadband noise from wind + rain) differs
qualitatively from either phenomenon alone.

### 3.2 Guidance as Atmospheric Stability

The `guidance` parameter (0-6) controls how closely the generative model adheres to its
prompts. We tie it to rain probability:

```
guidance = 3.0 + rain * 2.0
```

Clear skies (rain = 0) yield guidance = 3.0, allowing the model creative latitude ---
analogous to the unpredictable, open character of a calm day. Rainy conditions push
guidance to 5.0, forcing the model to follow the prescribed mood more tightly, reflecting
how precipitation constrains atmospheric dynamics into more predictable patterns
(laminar flow in stable precipitation vs chaotic convection in clear unstable air is
the inverse, but musically the tighter constraint produces a more coherent "rainy day"
mood that listeners expect).

---

## 4. Pulse Lens: Cardiac Electrophysiology

### 4.1 The ECG Waveform Model

A single cardiac cycle produces the characteristic PQRST waveform on an
electrocardiogram. Each component corresponds to a phase of cardiac electrical activity:

```
P wave:   Atrial depolarization (SA node -> atrial muscle)
QRS:      Ventricular depolarization (AV node -> bundle of His -> Purkinje fibers)
T wave:   Ventricular repolarization (recovery of resting potential)
```

We model this as a piecewise function of the normalized phase
`phi = (t mod RR) / RR`, where `RR = 60/HR` is the R-R interval in seconds:

```
ECG(phi) = {
    0.15 * sin(pi * (phi - 0.10) / 0.10)    if  0.10 < phi < 0.20   (P wave)
   -0.10 * (phi - 0.25) / 0.03              if  0.25 < phi < 0.28   (Q descent)
   -0.10 + 1.20 * (phi - 0.28) / 0.02       if  0.28 < phi < 0.30   (R ascent)
    1.10 - 1.30 * (phi - 0.30) / 0.05       if  0.30 < phi < 0.35   (S descent)
    0.25 * sin(pi * (phi - 0.45) / 0.15)     if  0.45 < phi < 0.60   (T wave)
    0.0                                       otherwise               (isoelectric)
}
```

**Implementation** (`lenses/pulse.py:57-69`):

```python
def _ecg_waveform(self, t: float, rr_interval: float) -> float:
    phase = (t % rr_interval) / rr_interval
    if 0.1 < phase < 0.2:
        return 0.15 * math.sin((phase - 0.1) / 0.1 * math.pi)       # P wave
    if 0.25 < phase < 0.28:
        return -0.1 * ((phase - 0.25) / 0.03)                        # Q
    if 0.28 < phase < 0.30:
        return -0.1 + 1.2 * ((phase - 0.28) / 0.02)                  # R
    if 0.30 < phase < 0.35:
        return 1.1 - 1.3 * ((phase - 0.30) / 0.05)                   # S
    if 0.45 < phase < 0.60:
        return 0.25 * math.sin((phase - 0.45) / 0.15 * math.pi)      # T wave
    return 0.0
```

The P wave and T wave are modeled as half-sinusoids (smooth, rounded deflections), while
the QRS complex uses linear segments (reflecting the rapid, near-discontinuous
depolarization wavefront propagating through ventricular muscle at ~2 m/s). The relative
amplitudes (P ~0.15, R ~1.1, T ~0.25) match clinical ECG amplitude ratios in Lead II.

### 4.2 Heart Rate to Tempo: The Isomorphic Mapping

The most physically direct mapping in the entire system:

```
BPM_music = HR_cardiac
```

This is a 1:1 identity mapping clamped to [60, 200]. The music literally beats with the
heart. At resting HR = 72 bpm, you hear a relaxed tempo. At exercise HR = 160, you hear
a driving beat.

This mapping exploits **entrainment** --- the tendency of biological and mechanical
oscillators to synchronize. Listeners report feeling their own heart rate "lock on" to
the musical beat when the match is close (Trost et al., 2017). By making the mapping
exact, we maximize this entrainment potential.

**Implementation** (`lenses/pulse.py:78`):

```python
bpm = int(self._ema("bpm", max(60, min(200, hr))))
```

### 4.3 Heart Rate Variability: The Complexity Signal

Heart Rate Variability (HRV) measures the beat-to-beat variation in R-R intervals.
Contrary to naive expectation, a healthy heart is **not** metronomically regular.
Healthy cardiac rhythm exhibits fractal-like variability driven by the interplay of
sympathetic and parasympathetic autonomic tone.

The standard metric is SDNN --- the standard deviation of all normal-to-normal R-R
intervals, measured in milliseconds:

```
SDNN = sqrt( (1/N) * sum_{i=1}^{N} (RR_i - mean(RR))^2 )
```

Clinically, SDNN ranges from ~10 ms (severe autonomic dysfunction) to ~80+ ms (healthy
resting adult). We parameterize this via the `hrv` slider (0-1):

```
SDNN = hrv * 80  (ms)
```

We map SDNN to musical **density** (the number of simultaneous voices / textural
complexity):

```
density = SDNN / 80 = hrv
```

**Physical justification:** High HRV reflects a complex, adaptive autonomic nervous
system with rich dynamical structure --- multiple regulatory loops operating at different
timescales (respiratory sinus arrhythmia at ~0.25 Hz, baroreceptor reflex at ~0.1 Hz,
thermoregulatory oscillations at ~0.04 Hz). This multi-scale complexity maps naturally
to musical density: more simultaneous voices at different rhythmic levels represent the
multi-frequency autonomic regulation.

Low HRV (as in heart failure, severe stress, or extreme exertion) reflects a locked,
simplified autonomic state --- the system is dominated by sympathetic drive with reduced
parasympathetic modulation. The sparse musical texture mirrors this loss of complexity.

### 4.4 Stress and Musical Tonality

Psychological stress activates the sympathetic nervous system, increasing heart rate,
reducing HRV, and elevating circulating catecholamines. We map stress to musical
**scale** (tonality):

```
scale = C Major / A minor   if stress < 0.5
        Ab Major / F minor   if stress >= 0.5
```

This exploits the well-documented association between musical mode and emotional valence.
Major keys in "bright" registers (C, D, E) are perceived as positive and relaxed. Flat
keys (Ab, Db) are perceived as darker and more tense. The Ab Major / F minor pairing
introduces the "Neapolitan" quality --- the lowered second degree (Db in C context)
that has been associated with grief and tension since the Baroque era.

The stress-to-guidance mapping further tightens the model's adherence to the prescribed
mood:

```
guidance = 3.5 + stress * 1.5
```

Under stress, guidance reaches 5.0, forcing the model into the prescribed tense mood
with less creative wandering.

### 4.5 Arrhythmia as Timbral Disruption

Cardiac arrhythmias (premature ventricular contractions, atrial fibrillation) are
departures from the normal sinus rhythm. They are sonically represented as **glitch**
events --- abrupt timbral disruptions injected as weighted prompts:

```python
if arrhythmia:
    prompts.append({"text": "Glitchy effects, weird noises", "weight": 0.7})
```

The arrhythmia probability is user-controllable (0-20%), allowing exploration of how
rhythmic disruption affects both the ECG visualization and the musical output. This
models the clinical reality that PVCs are relatively common (present in ~1-4% of beats
in healthy individuals, higher under stress or caffeine).

---

## 5. Lattice Lens: Dynamical Systems Theory

### 5.1 The Lorenz System

The Lorenz system is a three-dimensional autonomous ODE that Edward Lorenz derived in
1963 as a severely truncated model of Rayleigh-Benard convection (thermal convection in
a fluid layer heated from below). The equations are:

```
dx/dt = sigma * (y - x)
dy/dt = x * (rho - z) - y
dz/dt = x * y - beta * z
```

where:
- **sigma** (Prandtl number) = ratio of kinematic viscosity to thermal diffusivity.
  Default: 10.0. Controls the rate of momentum diffusion relative to heat diffusion.
- **rho** (Rayleigh number, normalized) = driving force of convection. Default: 28.0.
  This is the primary bifurcation parameter.
- **beta** (geometric factor) = aspect ratio of the convection cell. Default: 8/3.

The system exhibits qualitatively different behavior depending on rho:

| rho range | Behavior | Physical interpretation |
|-----------|----------|------------------------|
| 0 < rho < 1 | Origin is stable | No convection (heat conduction dominates) |
| 1 < rho < 13.93 | Stable fixed points | Steady convection (two symmetric rolls) |
| 13.93 < rho < 24.06 | Transient chaos | Metastable convection with occasional flips |
| rho > 24.74 | Strange attractor | Chaotic convection (butterfly attractor) |

We map the user's chaos slider (0 to 1) to rho:

```
rho = 10 + 35 * chaos
```

This spans rho from 10 (stable fixed point, pure conduction) to 45 (deep chaos). The
transition through the bifurcation cascade at rho ~ 24.74 is where the system transitions
from periodic orbits to the famous strange attractor.

**Numerical Integration** (`data_sources/simulators.py:142-152`):

```python
def step(self) -> tuple[float, float, float]:
    dx = self.sigma * (self.y - self.x)
    dy = self.x * (self.rho - self.z) - self.y
    dz = self.x * self.y - self.beta * self.z
    self.x += dx * self.dt
    self.y += dy * self.dt
    self.z += dz * self.dt
```

We use the forward Euler method with dt = 0.005. While Euler is only first-order
accurate (O(dt) local error, O(1) global error), the Lorenz attractor is structurally
stable --- its topological properties (two lobes, the butterfly shape) are preserved
under small numerical perturbations. Since we are interested in qualitative trajectory
character (not precise orbit tracking), Euler suffices. Higher-order methods (RK4) would
be needed for quantitative Lyapunov exponent computation but are unnecessary for
sonification.

### 5.2 Chaos Metric: Trajectory Variance as a Proxy for Lyapunov Exponent

The maximal Lyapunov exponent lambda_1 quantifies the rate of exponential divergence of
nearby trajectories:

```
|delta(t)| ~ |delta(0)| * exp(lambda_1 * t)
```

For the Lorenz system, lambda_1 ~ 0.9056 at the standard parameters (sigma=10, rho=28,
beta=8/3). Computing lambda_1 online requires tracking a tangent vector, which is
expensive.

Instead, we use a **trajectory variance proxy**. We compute the step-to-step Euclidean
displacement over the last 10 trajectory points:

```python
diffs = [
    sqrt((b[0]-a[0])^2 + (b[1]-a[1])^2 + (b[2]-a[2])^2)
    for a, b in zip(recent, recent[1:])
]
variance = (1/N) * sum((d - mean(diffs))^2 for d in diffs)
chaos_metric = min(1.0, variance / 5.0)
```

**Why this works:** On a periodic orbit, step-to-step displacements are nearly constant
(the trajectory traces the same path at the same speed), so their variance is near zero.
On the chaotic attractor, the trajectory alternates unpredictably between the two lobes,
with wildly varying velocities near the saddle point at the origin. The displacement
variance captures this irregularity.

The normalization `variance / 5.0` is empirically calibrated so that the standard chaotic
attractor (rho=28) produces chaos_metric ~ 0.6-0.8, while the periodic regime
(rho < 24) produces chaos_metric < 0.2.

### 5.3 Sonification Mapping

The chaos metric drives every musical dimension simultaneously:

```
BPM        = 80 + chaos_level * 80        (80-160)
density    = chaos_level                   (0-1)
brightness = amplitude                     (0-1, from ||x,y,z|| / 50)
scale      = C Major (order) -> Gb Major (chaos)
temperature = 0.8 + chaos_level * 1.0     (model randomness)
```

**Scale progression:** The three musical scales form a tonal tension gradient:

- **C Major / A minor** (chaos < 0.3): The "home key." No sharps or flats. Maximum
  consonance. Matches the ordered, predictable trajectory of a periodic orbit.

- **D Major / B minor** (0.3 < chaos < 0.6): Two sharps. Brighter, more complex tonality.
  Matches the transitional regime where the system is between periodic and chaotic.

- **Gb Major / Eb minor** (chaos > 0.6): Six flats. The most "distant" key from C in
  the circle of fifths (a tritone away). Maximum tonal tension. Matches the
  unpredictable, space-filling trajectory of the strange attractor.

**Prompt evolution:** The textual prompts follow the same gradient:
- Order: "Piano, melodic, classical, ordered" + "Sustained chords, harmonic"
- Transition: "Jazz fusion, complex, experimental" + "Rhodes piano, synth pads"
- Chaos: "Glitchy effects, experimental, weird noises" + "Psychedelic, echo, distortion"

**Guidance:** `3.0 + chaos * 2.0`. In the ordered regime, low guidance (3.0) lets the
model add subtle variations to the clean piano texture. In the chaotic regime, high
guidance (5.0) forces the model to stay committed to the prescribed chaotic style,
preventing it from "resolving" the tension prematurely.

### 5.4 The Logistic Map

The logistic map is the simplest system exhibiting the full Feigenbaum period-doubling
cascade to chaos:

```
x_{n+1} = r * x_n * (1 - x_n)
```

where `r` is the growth parameter. The bifurcation diagram reveals:

| r range | Behavior |
|---------|----------|
| 0 < r < 1 | Extinction (x -> 0) |
| 1 < r < 3 | Stable fixed point at x* = 1 - 1/r |
| 3.0 < r < 3.449 | Period-2 cycle |
| 3.449 < r < 3.544 | Period-4 cycle |
| 3.544 < r < 3.564 | Period-8, 16, ... (Feigenbaum cascade) |
| r > 3.5699... | Onset of chaos (with periodic windows) |
| r = 4.0 | Full chaos (ergodic on [0,1]) |

We map the chaos slider to r via:

```
r = 2.5 + chaos * 1.5
```

spanning r from 2.5 (stable fixed point) to 4.0 (full chaos). The chaos_level is
estimated by the **unique value ratio** of the last 20 iterations:

```python
unique_ratio = len(set(round(v, 2) for v in recent)) / len(recent)
```

A period-1 orbit produces unique_ratio ~ 0.05 (all values identical to 2 decimal places).
A period-2 orbit produces ~0.10. A chaotic orbit produces ~0.85-1.0 (nearly all values
distinct). This ratio is a computationally cheap proxy for the **topological entropy** of
the map.

The sonification mapping is identical to the Lorenz case: chaos_level drives BPM,
density, scale, and prompts through the same transfer functions. The prompt texture for
the logistic map adds "Minimal techno, precise, electronic" to reflect the discrete,
iterative character of the map (as opposed to the continuous flow of the Lorenz ODE).

### 5.5 Sine Superposition

The sine superposition mode implements **additive synthesis as data source**, creating a
deterministic signal from the sum of sinusoids with incommensurate frequencies:

```
f(t) = sum_{i=0}^{N-1}  (1 / (i+1)) * sin(t * omega_i)
```

where `omega_i = 0.5 + i * 0.7 + chaos * i * 0.3` and `N = 3 + floor(5 * chaos)`.

The chaos parameter controls both the number of components (3 to 8) and their frequency
spacing. When frequencies are nearly commensurate (low chaos), the superposition is
quasi-periodic with a recognizable repeating pattern. When frequencies become
increasingly incommensurate (high chaos), the signal is quasi-chaotic --- bounded but
never exactly repeating (by the Kolmogorov-Arnold-Moser theorem, systems with
sufficiently many incommensurate frequencies are generically non-integrable).

The `1/(i+1)` amplitude weighting produces a spectral envelope similar to a sawtooth
wave (amplitude falls as 1/n), giving the signal a natural, instrument-like harmonic
structure.

---

## 6. Flow Lens: Queueing Theory and Network Dynamics

### 6.1 Poisson Process Model

Network packet arrivals are classically modeled as a **Poisson process** --- a
memoryless point process where the probability of exactly k arrivals in a time
interval of length dt is:

```
P(N(dt) = k) = (lambda * dt)^k * exp(-lambda * dt) / k!
```

where `lambda` is the arrival rate (packets per second).

The Poisson model arises from three axioms: (1) events in non-overlapping intervals are
independent, (2) the probability of exactly one event in [t, t+h) is lambda*h + o(h),
(3) the probability of two or more events in [t, t+h) is o(h). In real networks, these
axioms hold approximately for aggregate traffic at moderate timescales (~seconds), though
at sub-millisecond scales, traffic exhibits self-similar (long-range dependent) behavior
described by fractional Brownian motion.

**Knuth's Algorithm for Poisson variates** (`data_sources/simulators.py:330-343`):

```python
def _poisson(self, lam: float) -> int:
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= self._rng.random()
    return k - 1
```

This exploits the fact that inter-arrival times in a Poisson process are exponentially
distributed. The product of k uniform random variables on [0,1] follows the same
distribution as exp(-S_k) where S_k is the sum of k exponential(1) variables. The
algorithm terminates when this product drops below exp(-lambda), which happens after
a Poisson(lambda)-distributed number of iterations.

For large lambda (> 500), the algorithm switches to the Gaussian approximation
(Poisson(lambda) ~ N(lambda, sqrt(lambda)) for large lambda, by the central limit
theorem).

### 6.2 Burst Modeling

Network traffic bursts --- sudden surges caused by TCP congestion window resets,
application-level batch transfers, or DDoS attacks --- are modeled as a **switched
Poisson process**. The system alternates between a normal state (rate = lambda) and a
burst state (rate = 3 * lambda):

```python
if t > self._burst_until and self._rng.random() < 0.01:
    self._burst_until = t + self._rng.uniform(1, 5)
    rate *= 3
```

Burst onset is a Bernoulli trial with p = 0.01 per tick. Burst duration is
uniform[1, 5] seconds. This is a simplified version of the **Markov Modulated Poisson
Process** (MMPP) commonly used in telecommunications modeling (Fischer & Meier-Hellstern,
1993), where the arrival rate switches between states according to a continuous-time
Markov chain.

### 6.3 Sonification Mappings

**Packet Rate to Density: Information Throughput as Textural Richness**

```
density = packet_rate / 200
```

This is the most direct mapping in the flow lens. The packet rate measures the amount of
information flowing through the network. More packets = more simultaneous conversations
between nodes = more musical voices. At 200 packets/s (maximum load), density = 1.0
(full orchestral texture). At 1 packet/s (idle), density ~ 0.005 (near silence with
occasional sparse notes).

**Latency to Brightness: Responsiveness as Timbral Clarity**

```
brightness = max(0, 1.0 - latency / 200)
```

Network latency is the round-trip time for a packet to reach its destination and return.
Low latency (1 ms, fiber-optic LAN) produces brightness = 0.995 (sharp, clear attack).
High latency (200 ms, congested WAN) produces brightness = 0.0 (muffled, sluggish
timbre).

The inverse mapping captures the perceptual analogy: a responsive, fast network "feels"
crisp and immediate, just as bright timbres have fast transients and strong high-frequency
content. A sluggish network "feels" muddy, just as dark timbres have slow attacks and
roll off above 2-3 kHz.

**Latency in M/M/1 queue theory** follows the relation:

```
E[W] = 1 / (mu - lambda)
```

where `mu` is the service rate and `lambda` is the arrival rate. As the network
approaches saturation (lambda -> mu), latency diverges hyperbolically. Our direct slider
control lets the user explore this relationship: increasing packet_rate while keeping
latency constant is physically unrealistic but sonically instructive, while increasing
both together mimics realistic congestion.

**Burst Detection to Tempo Spike**

```
base_bpm = 80 + load * 40
burst_bpm = base_bpm + 50
```

Bursts cause an immediate +50 BPM spike (subject to EMA smoothing, so the ramp-up takes
~2-3 seconds). This models the **alarm response** to a sudden traffic surge: network
operators monitoring dashboards experience bursts as urgent events requiring attention,
and the tempo spike creates the same visceral urgency.

**Error Rate to Timbral Glitch**

```python
if error_rate > 0.05:
    prompts.append({"text": "Glitchy effects, metallic twang", "weight": error_rate * 5})
```

Packet errors (checksum failures, timeouts, drops) are discrete failure events ---
analogous to skipped notes, wrong pitches, or digital artifacts in audio. The prompt
weight scales linearly with error rate (weight 0 at error_rate = 0.05, weight 1.0 at
error_rate = 0.20), so the glitch intensity directly reflects error severity.

### 6.4 Network Load as an Intensive Variable

The `load_level` metric normalizes packet_rate to [0, 1]:

```
load = min(1.0, packet_rate / 200)
```

This is analogous to system utilization `rho = lambda / mu` in queueing theory.
At rho < 0.3 (light load), the system is well below capacity --- queues are short,
latency is low. At rho > 0.7 (heavy load), the system is near saturation --- queues
grow, latency spikes, errors increase.

The prompt progression follows this gradient:
- rho < 0.3: "Ambient, minimal, spacey synths" (the quiet hum of an idle data center)
- 0.3 < rho < 0.7: "Chiptune, electronic, steady" (regular traffic, digital rhythm)
- rho > 0.7: "Drum & Bass, intense, fast" (saturated network, urgency)

---

## 7. Mock Audio Engine: Additive Synthesis Driven by ControlState

When neither Lyria nor ElevenLabs is available, the `MockAudioGenerator` provides a
rule-based synthesizer that receives the **exact same ControlState**. Of the 9 fields in
ControlState, the mock engine applies 8. Only `prompts` is dropped --- it requires a
generative AI model to interpret natural language and no rule-based synth can replicate
that capability. This section is explicit about what is and is not applied.

### 7.1 ControlState Coverage: What the Mock Applies

| ControlState Field | Applied? | Mock Synth Parameter | Justification |
|---|---|---|---|
| `bpm` | **Yes** | LFO rate | Rhythmic pulse at the beat rate |
| `brightness` | **Yes** | Base pitch (pre-quantization) | Higher pitch = brighter timbre |
| `density` | **Yes** | Harmonic count | More harmonics = richer texture |
| `scale` | **Yes** | Pitch quantization | Snaps frequency to scale tones |
| `guidance` | **Yes** | LFO depth and regularity | High = steady, low = erratic |
| `temperature` | **Yes** | Noise floor amplitude | More temperature = noisier |
| `mute_bass` | **Yes** | Removes low harmonics | Strips fundamental + 2nd harmonic |
| `mute_drums` | **Yes** | Suppresses LFO pulsing | Eliminates rhythmic modulation |
| `prompts` | **No** | --- | Requires generative AI to interpret natural language |

**Why prompts cannot be applied:** Prompts are free-text descriptions like "Piano
arpeggios, rain, gentle" or "Glitchy effects, crunchy distortion." Interpreting these
requires a generative model that understands musical semantics --- what "rain" means as
a sonic texture, what "crunchy" means as a spectral quality. A rule-based synthesizer
with a fixed architecture (additive synthesis + LFO) cannot reconstruct arbitrary
timbres from text. Keyword matching (e.g., detecting "glitch" and adding noise bursts)
would be fragile and dishonest --- it would suggest coverage that does not exist. We
prefer to be explicit: prompts are a Lyria-only feature.

**Practical consequence:** In mock mode, the *transfer functions* that produce prompts
still run (e.g., the storm detection logic `wind > 20 AND rain > 0.5` still fires), but
the resulting prompt has no audible effect. The 8 other control dimensions --- including
scale changes, guidance variations, temperature shifts, and bass/drum muting --- are
all fully audible.

### 7.2 Additive Synthesis with Dynamic Harmonics

The core synthesis equation:

```
s(t) = V * LFO(t) * [ sum_{k in K} (a_k / k) * sin(2*pi*k*f*t) + noise(t) ]
```

where:
- `f = quantize(110 + brightness * 330, scale)` Hz (pitch, quantized to active scale)
- `K = {3, 4, ..., N}` if mute_bass, else `{1, 2, ..., N}` (harmonic indices)
- `N = 1 + floor(density * 5)` (number of harmonics, 1 to 6)
- `a_k = 0.3 / k` (amplitude of k-th harmonic, 1/k spectral roll-off)
- `V = 0.3` (master volume)
- `noise(t) = N(0, temperature / 20)` (Gaussian noise, amplitude from temperature)
- `LFO(t)` is detailed below (controlled by bpm, guidance, mute_drums)

### 7.3 Scale Quantization: Equal Temperament Pitch Snapping

The raw frequency from brightness is continuous (110-440 Hz). When a scale is active,
the frequency is snapped to the nearest pitch in that scale using equal temperament.

**Algorithm:**

1. Convert frequency to MIDI note number: `n = 69 + 12 * log2(f / 440)`
2. Extract pitch class: `pc = round(n) mod 12`
3. Find the nearest pitch class in the scale's note set (wrapping at octave boundary)
4. Adjust the MIDI note to that pitch class
5. Convert back: `f = 440 * 2^((n_quantized - 69) / 12)`

Each Lyria scale maps to a set of pitch classes (semitones from C):

| Scale | Pitch classes | Notes |
|-------|--------------|-------|
| `C_MAJOR_A_MINOR` | {0, 2, 4, 5, 7, 9, 11} | C D E F G A B |
| `D_MAJOR_B_MINOR` | {1, 2, 4, 6, 7, 9, 11} | C# D E F# G A B |
| `A_FLAT_MAJOR_F_MINOR` | {0, 1, 3, 5, 7, 8, 10} | Ab Bb C Db Eb F G |
| `G_FLAT_MAJOR_E_FLAT_MINOR` | {1, 3, 5, 6, 8, 10, 11} | Gb Ab Bb Cb Db Eb F |
| `SCALE_UNSPECIFIED` | all 12 | no quantization |

**Effect:** When the Pulse lens switches from C Major (relaxed) to Ab Major (stressed),
the mock synth's available pitches change. The listener hears the same pitch shift to a
darker tonal center --- a genuine tonal change, not a cosmetic one.

**Implementation** (`lyria_bridge.py:45-69`):

```python
def _quantize_to_scale(self, freq: float, scale_notes: set[int] | None) -> float:
    if scale_notes is None or freq <= 0:
        return freq
    midi = 69.0 + 12.0 * math.log2(freq / 440.0)
    midi_rounded = round(midi)
    pitch_class = midi_rounded % 12
    best_dist = 12
    best_pc = pitch_class
    for pc in scale_notes:
        dist = min(abs(pc - pitch_class), 12 - abs(pc - pitch_class))
        if dist < best_dist:
            best_dist = dist
            best_pc = pc
    diff = best_pc - pitch_class
    if diff > 6:
        diff -= 12
    elif diff < -6:
        diff += 12
    quantized_midi = midi_rounded + diff
    return 440.0 * (2.0 ** ((quantized_midi - 69) / 12.0))
```

### 7.4 LFO: Guidance-Controlled Rhythmic Modulation

The Low-Frequency Oscillator provides amplitude modulation at the beat rate:

```
LFO(t) = 0.5 + D * 0.5 * sin(2*pi * f_LFO * t) + (1 - D) * jitter(t)
```

where:
- `f_LFO = BPM / 60` Hz (LFO rate tracks the musical tempo)
- `D = min(1, guidance / 6)` (LFO depth, from guidance)
- `jitter(t) = N(0, 0.3)` (random irregularity, scaled by `1 - D`)

**Guidance mapping:** In Lyria, high guidance forces the model to follow prompts
tightly --- producing predictable, structured output. Low guidance lets the model
wander. The mock mirrors this: high guidance (D ~ 1) produces a deep, metronomic pulse
(fully predictable). Low guidance (D ~ 0) produces shallow, irregular amplitude
fluctuations (unpredictable). The result is clamped to [0.1, 1.0] to prevent silence
or clipping.

**mute_drums override:** When `mute_drums = True`, the LFO is bypassed entirely
(`LFO(t) = 1.0`), removing all rhythmic pulsing. In Lyria, this silences the drum
track. In the mock, it converts the pulsing tone into a sustained drone.

### 7.5 Temperature as Noise Injection

Lyria's `temperature` parameter controls the randomness of the generative process ---
low temperature produces predictable, conservative output; high temperature produces
surprising, potentially incoherent results.

The mock maps this to a Gaussian noise floor mixed into the signal:

```
noise_amplitude = temperature / 20
```

At temperature = 0: pure tonal output (no noise). At temperature = 3.0 (maximum):
15% noise floor relative to signal amplitude. The noise is uncorrelated (white),
adding broadband spectral energy that masks the harmonic structure --- mimicking how
high Lyria temperature produces less tonally coherent output.

### 7.6 Bass Muting: Harmonic Filtering

When `mute_bass = True` and at least 3 harmonics are active, the fundamental (k=1)
and second harmonic (k=2) are removed from the synthesis:

```
K = {1, 2, 3, ..., N}  -->  K = {3, 4, ..., N}
```

This shifts the perceived pitch up by approximately an octave + fifth (the ear tracks
the lowest present harmonic) and thins the timbre. In Lyria, `mute_bass` silences the
bass instrument track. The mock's harmonic filtering is a coarser approximation but
produces an audible and directionally correct effect --- the low-frequency energy
disappears.

### 7.7 Frequency Portamento

The frequency does not jump instantaneously when brightness changes. Instead, it glides
toward the target via a first-order lag:

```python
freq_step = (self._target_freq - self._freq) * 0.01
self._freq += freq_step * 0.001
```

This is a double-smoothed portamento: the EMA in the lens smooths the brightness value,
and the lag filter in the synth smooths the frequency. The combined effect is a glissando
that takes approximately 1-2 seconds to reach a new frequency target, matching the
perceptual expectation that pitch changes should be gradual in ambient music.

### 7.8 Phase Accumulator Design

The synthesizer uses a phase accumulator to generate waveforms:

```python
self._phase += math.tau * self._freq / self.sample_rate
```

This is the standard numerically controlled oscillator (NCO) design used in digital
signal processing. The phase is accumulated modulo 2*pi*1000 (rather than modulo 2*pi)
to prevent floating-point precision loss when the phase value grows large:

```python
if self._phase > math.tau * 1000:
    self._phase -= math.tau * 1000
```

At 48 kHz sample rate and 440 Hz fundamental, the phase accumulates at
440 * 2*pi / 48000 = 0.0576 radians per sample. After ~109,000 samples (~2.3 seconds),
the unwrapped phase would reach 2*pi*1000 and is folded back. This prevents the gradual
loss of significant digits that would cause pitch drift in a long-running session.

---

## 8. ElevenLabs Bridge: Batch Generation from ControlState

### 8.1 Architectural Differences from Lyria

Lyria RealTime is a streaming session: the server pushes control parameter updates and
receives a continuous PCM audio stream with ~50ms latency. The audio adapts in real time
to parameter changes.

The ElevenLabs Music API is fundamentally different: it accepts a text prompt and a
duration, then returns a complete audio segment. There are no live control knobs. This
means the bridge must:

1. **Convert ControlState to text** — translate numeric parameters into natural language
   descriptors that the Music API can interpret.
2. **Generate in segments** — produce 30-second audio blocks and queue them for playback.
3. **Debounce parameter changes** — avoid aborting generation on every slider tick.

### 8.2 Prompt Construction: ControlState to Natural Language

The `_build_prompt()` method maps each ControlState field to a descriptive text fragment:

| ControlState Field | Prompt Fragment | Thresholds |
|---|---|---|
| `prompts` | Lens text prompts (sorted by weight) | All included |
| `bpm` | "slow tempo" / "moderate" / "upbeat" / "fast energetic" | <80 / <110 / <140 / >=140 |
| `density` | "sparse minimal arrangement" / "dense layered arrangement" | <0.3 / >0.7 |
| `brightness` | "dark muted tones" / "bright shimmering tones" | <0.3 / >0.7 |
| `scale` | Key + mood text (e.g., "C major, uplifting mood") | Exact match |
| `mute_bass` | "no bass" | Boolean |
| `mute_drums` | "no drums" | Boolean |
| `temperature` | "experimental, unconventional" / "structured, predictable" | >2.0 / <0.5 |

The fragments are joined with commas and "instrumental" is always appended to suppress
vocals. Mid-range values (e.g., density between 0.3 and 0.7) produce no descriptor,
letting the model choose a neutral arrangement.

**Design tradeoff:** The threshold-based mapping intentionally uses coarse buckets rather
than continuous interpolation. A density change from 0.45 to 0.55 produces the same
prompt (no descriptor for either), avoiding unnecessary regeneration. Only crossing a
bucket boundary (e.g., density rising above 0.7) changes the prompt and triggers new
generation.

### 8.3 Debounce and Gapless Playback

The critical engineering challenge is maintaining gapless audio while allowing parameter
changes. The solution uses three mechanisms:

**Debounced prompt commits (2 seconds):** When `update()` receives new controls, it
records the pending prompt and a timestamp. The generation loop only commits the new
prompt after 2 seconds of no further changes. This absorbs slider drags (which fire at
5Hz) into a single regeneration event.

**Never abort mid-segment:** Once a segment starts queuing its PCM chunks to the audio
queue, it always finishes. The generation loop checks for debounced prompt changes only
*between* segments, not during chunk queuing. This ensures the current 30-second segment
plays to completion.

**Generation counter:** A monotonic counter (`_gen_id`) is incremented on `reset()`
(lens switch). If an API call returns after a reset, the stale response is discarded by
comparing the counter value captured before the call to the current value.

The resulting timeline for a slider change:

```
t=0s    User starts dragging slider
t=0-2s  Prompt changes accumulate (debounce timer resets on each change)
t=2s    User stops. Debounce timer expires. Prompt committed.
t=2s    Current segment continues playing (no interruption)
t=Xs    Current segment ends. New segment generated with updated prompt.
t=X+5s  New segment arrives, begins queuing. Gapless transition.
```

### 8.4 PCM Format Compatibility

The ElevenLabs Music API supports `output_format="pcm_48000"` which returns raw 16-bit
signed little-endian PCM at 48kHz. This is the exact format expected by the browser's
AudioWorklet processor — no MP3 decoding, resampling, or format conversion is needed.

The bridge detects mono output (by checking if sample count is odd or if byte alignment
matches mono frame size) and duplicates channels to stereo when necessary. The audio is
then split into 9600-byte chunks (2400 stereo frames = 50ms), matching the mock
generator's chunk geometry.

---

## 9. Audio Transport: PCM Streaming Architecture

### 8.1 Sample Format

Audio is streamed as raw Linear PCM:
- **Bit depth:** 16-bit signed integer (range: -32768 to +32767)
- **Sample rate:** 48,000 Hz
- **Channels:** 2 (interleaved stereo: L, R, L, R, ...)
- **Byte order:** Little-endian (Intel native)
- **Chunk size:** 2400 samples = 2400 * 2 channels * 2 bytes = 9600 bytes per chunk

At 48 kHz, a 2400-sample chunk represents 50 ms of audio. The system generates 20
chunks per second, yielding 192 kB/s of raw audio data over the WebSocket.

### 8.2 AudioWorklet Ring Buffer

The browser's `AudioWorkletProcessor` receives PCM chunks asynchronously via
`MessagePort` and writes them into a circular buffer. The `process()` method reads
from this buffer at exactly 48 kHz (enforced by the Web Audio API's real-time thread).

The ring buffer provides 5 seconds of capacity (48000 * 2 channels * 5 = 480,000
samples), absorbing jitter in WebSocket delivery without audible dropouts. If the buffer
underflows (network stall), the processor outputs silence rather than repeating stale
data, preventing the jarring "stuck record" artifact.

---

## 10. Summary of Transfer Functions

For reference, every deterministic mapping in the system:

### Atmosphere

| Input | Output | Transfer Function |
|-------|--------|-------------------|
| wind_speed (0-30 m/s) | BPM (70-180) | `70 + v * 3.67` |
| temperature (-10 to 40 C) | brightness (0-1) | `(T + 10) / 50` |
| humidity (0-100%) | density (0-1) | `H / 100` |
| rain (0-1) | guidance (3-5) | `3.0 + rain * 2.0` |
| rain > 0.3 | prompt injection | "Piano arpeggios" @ weight = rain |
| wind > 20 AND rain > 0.5 | prompt injection | "Dirty synths, distortion" @ 0.8 |

### Pulse

| Input | Output | Transfer Function |
|-------|--------|-------------------|
| heart_rate (40-200 bpm) | BPM (60-200) | identity, clamped |
| hrv (0-1) * 80 ms = SDNN | density (0-1) | `SDNN / 80` |
| stress (0-1) | brightness (0.3-0.9) | `0.3 + stress * 0.6` |
| stress (0-1) | guidance (3.5-5.0) | `3.5 + stress * 1.5` |
| stress > 0.5 | scale | C Maj -> Ab Maj/F min |
| arrhythmia (bool) | prompt injection | "Glitchy effects" @ 0.7 |

### Lattice

| Input | Output | Transfer Function |
|-------|--------|-------------------|
| chaos slider (0-1) | rho (10-45) | `10 + 35 * chaos` |
| trajectory variance | chaos_level (0-1) | `min(1, var(displacements) / 5)` |
| chaos_level (0-1) | BPM (80-160) | `80 + chaos * 80` |
| chaos_level (0-1) | density (0-1) | identity |
| amplitude = norm(x,y,z)/50 | brightness (0-1) | identity |
| chaos_level (0-1) | temperature (0.8-1.8) | `0.8 + chaos * 1.0` |
| chaos_level (0-1) | guidance (3-5) | `3.0 + chaos * 2.0` |

### Flow

| Input | Output | Transfer Function |
|-------|--------|-------------------|
| packet_rate (1-200/s) | density (0-1) | `rate / 200` |
| latency (1-200 ms) | brightness (0-1) | `1.0 - latency / 200` |
| load (0-1) | BPM (80-120) | `80 + load * 40` |
| burst (bool) | BPM | `+50` added to base |
| load (0-1) | guidance (3.5-5.0) | `3.5 + load * 1.5` |
| load (0-1) | temperature (1.0-1.5) | `1.0 + load * 0.5` |
| error_rate > 0.05 | prompt injection | "Glitchy" @ weight = error_rate * 5 |

### Mock Synthesizer (8 of 9 fields applied)

| Input | Output | Transfer Function |
|-------|--------|-------------------|
| brightness (0-1) | base frequency (110-440 Hz) | `110 + brightness * 330`, then quantized to scale |
| density (0-1) | harmonics (1-6) | `1 + floor(density * 5)` |
| bpm (60-200) | LFO rate (1-3.3 Hz) | `bpm / 60` |
| scale | pitch quantization | snaps frequency to nearest note in scale (equal temperament) |
| guidance (0-6) | LFO depth (0-1) | `min(1, guidance / 6)` ; also adds `(1-depth) * jitter` |
| temperature (0-3) | noise floor (0-0.15) | `temperature / 20` (Gaussian noise amplitude) |
| mute_bass (bool) | harmonic filter | removes harmonics k=1, k=2 if 3+ harmonics present |
| mute_drums (bool) | LFO bypass | `LFO(t) = 1.0` (no rhythmic pulsing) |
| prompts | **NOT APPLIED** | requires generative AI; no rule-based equivalent exists |

---

## References

1. Lorenz, E. N. (1963). "Deterministic Nonperiodic Flow." *Journal of the Atmospheric Sciences*, 20(2), 130-141.
2. May, R. M. (1976). "Simple mathematical models with very complicated dynamics." *Nature*, 261(5560), 459-467.
3. Hermann, T., Hunt, A., & Neuhoff, J. G. (2011). *The Sonification Handbook*. Logos Verlag.
4. Helmholtz, H. (1863). *On the Sensations of Tone*. Dover reprint, 1954.
5. Fischer, W. & Meier-Hellstern, K. (1993). "The Markov-Modulated Poisson Process (MMPP) Cookbook." *Performance Evaluation*, 18, 149-171.
6. Feigenbaum, M. J. (1978). "Quantitative universality for a class of nonlinear transformations." *Journal of Statistical Physics*, 19(1), 25-52.
7. Trost, W. et al. (2017). "Getting the beat: Entrainment of brain activity by musical rhythm and pleasantness." *NeuroImage*, 103, 55-64.
8. Task Force of the European Society of Cardiology (1996). "Heart rate variability: Standards of measurement." *Circulation*, 93(5), 1043-1065.
9. Knuth, D. E. (1997). *The Art of Computer Programming, Vol. 2: Seminumerical Algorithms*. Addison-Wesley.
