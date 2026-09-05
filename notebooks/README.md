# Tutorials

Modality-by-modality walkthroughs. Each notebook is self-contained, runs in
seconds, and builds its own data — no download, no network access, and no
patient data at any point.

| Notebook | What it covers |
| --- | --- |
| [`01_mri_augmentation.ipynb`](01_mri_augmentation.ipynb) | Why MR noise is Rician rather than Gaussian, bias fields, k-space ghosting and dropout, motion, mask alignment, seeding, and saving a policy to JSON. |
| [`02_ct_augmentation.ipynb`](02_ct_augmentation.ipynb) | Hounsfield units as calibrated physical values, windowing as both display and augmentation, beam hardening, metal streak, and guarding against implausible output. |
| [`03_dbt_augmentation.ipynb`](03_dbt_augmentation.ipynb) | Anisotropic 3D volumes, slab shift, limited-angle blur and its through-plane cost, slice dropout, compression variation, and anisotropic elastic deformation. |

## Running them

```bash
pip install -e ".[notebooks]"
jupyter lab notebooks/          # or: jupyter notebook notebooks/
```

The `notebooks` extra installs `matplotlib` plus the kernel and execution
machinery. It is optional — the core install still depends only on NumPy and
SciPy. `jupyter lab` itself is not included; install it separately if you want
the browser UI.

## Synthetic data

The volumes come from [`medaugmentx.phantoms`](../medaugmentx/phantoms.py),
which generates brain, abdomen, chest, and tomosynthesis phantoms from analytic
shapes and a fixed seed. They are illustrations, not validated physical models
of anatomy or scanner physics — useful for seeing what a transform does, not
for drawing clinical conclusions.

You can use them in your own experiments and tests:

```python
from medaugmentx.phantoms import ct_phantom
from medaugmentx.transforms import BeamHardening

volume = ct_phantom()
augmented = BeamHardening(alpha=0.10, seed=7)(volume)
```

Transform strengths in the tutorials are exaggerated so effects are visible in
a single figure. They are not recommended training policies — the right
strength depends on your dataset and task, so start weak and validate.

## Committed without outputs

Notebooks are stored with outputs stripped, which keeps diffs readable and the
repository small. The trade-off is that they render blank on GitHub; run them
to see the figures.

CI executes all three on every push so they cannot rot. To check them yourself
before opening a PR:

```bash
python notebooks/run_notebooks.py
```

If you edit a notebook in Jupyter, clear its outputs before committing
(*Kernel → Restart Kernel and Clear All Outputs*). `tests/test_phantoms.py`
fails if outputs or execution counts are committed.
