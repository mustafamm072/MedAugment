# Reproducible research

Start with one modality preset, establish a baseline without augmentation,
and add complexity only when a held-out evaluation supports it. Presets are
starting configurations; the library does not establish clinical validity or
promise improved model performance.

## Replay an experiment

A seed initializes a sequence of random draws. Two fresh pipelines with the
same configuration and integer seed reproduce that sequence in the same
software environment. Repeated calls to one pipeline advance its random state.
JSON/YAML saves constructor configuration and integer seeds, not the current
random state or the number of samples already processed. A supplied NumPy
`Generator` is serialized as `seed=None`; use integer seeds for saved policies.
A container's seed overrides its children's seeds. Reordering or inserting
children can change their assigned streams.

Run the complete synthetic example from the repository root:

```bash
python examples/reproducible_experiment.py > experiment.json
```

The example reloads the policy, checks that the output is identical, and emits
the policy, dependency versions, synthetic-data seed, and SHA-256 fingerprints.
A fingerprint detects differences; it does not prove scientific validity or
provide an authenticity signature. Bitwise equality across operating systems,
hardware, or dependency versions is not guaranteed.

For real studies, record the package version or commit, complete environment,
normalization, voxel spacing, target conventions, split construction, training
seed, and augmentation policy. Keep private dataset identifiers and manifests
in your controlled experiment store rather than publishing them with examples.

## Multiple workers and epochs

Create independent pipelines inside each data-loader worker. Copying a pipeline
into workers can duplicate random streams. Derive a seed from stable integer
identifiers using `numpy.random.SeedSequence([experiment_seed, epoch, worker_id])`,
then pass an integer from `generate_state(1)` to your preset. Record worker
count and sample order: changing either can change which draw reaches a sample.
For scheduling-independent augmentation, construct a pipeline per sample using
an additional stable sample index and omit the worker id from its seed. Avoid
Python's process-dependent `hash()` for seed derivation.

## Report a useful comparison

Keep train, validation, and test splits fixed across comparisons. Apply random
training augmentation only to the training split unless your evaluation
explicitly studies test-time augmentation. Report the unaugmented baseline,
each policy tested, the selection rule, repeated training seeds, and uncertainty
alongside the task metric. Keep preprocessing and model settings matched.

Use `VolumeValidator` and visual inspection to catch unusable outputs. Document
how often guards reject or revert samples in your own experiment loop; a
passing validation report only covers configured structural/statistical rules.
For non-linear deformations, bounding boxes use transformed corners and are
an approximation, not a guaranteed enclosure of all warped anatomy.

## Citation and contributions

GitHub can generate a software citation from the repository's
[CITATION.cff](https://github.com/mustafamm072/MedAugmentX/blob/main/CITATION.cff).
Record the actual version or commit used. The README also links the project's
existing archive DOI; verify that the archive corresponds to your experiment
before citing a specific release.

Useful contributions include synthetic reproductions of failures, clearly
specified modality assumptions, and reproducible benchmark scripts. Never post
patient images or identifiers in a public issue. See
[Contributing](../CONTRIBUTING.md) and [Security](../SECURITY.md).
