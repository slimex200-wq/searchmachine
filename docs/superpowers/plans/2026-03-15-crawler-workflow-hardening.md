# Crawler Workflow Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the GitHub Actions crawler workflow easier to debug and ready for the Node 24 JavaScript action runtime transition.

**Architecture:** Keep the existing single-job workflow, but harden it with early diagnostics, deterministic log file creation, and non-fragile artifact upload behavior. Lock the intended workflow contract with a repository test that validates action versions and critical run-script content.

**Tech Stack:** GitHub Actions YAML, Python `unittest`, repository text assertions

---

## Chunk 1: Workflow Contract Test

### Task 1: Add failing workflow assertions

**Files:**
- Create: `tests/test_crawler_workflow.py`
- Test: `tests/test_crawler_workflow.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workflow_uses_node24_ready_action_versions():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_crawler_workflow -v`
Expected: FAIL because the workflow still references older action versions and lacks diagnostics.

- [ ] **Step 3: Write minimal implementation**

Update `.github/workflows/crawler.yml` so the file content satisfies the new assertions.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_crawler_workflow -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_crawler_workflow.py .github/workflows/crawler.yml docs/superpowers/plans/2026-03-15-crawler-workflow-hardening.md
git commit -m "ci: harden crawler workflow diagnostics"
```

## Chunk 2: Workflow Hardening

### Task 2: Improve diagnostics and artifact reliability

**Files:**
- Modify: `.github/workflows/crawler.yml`
- Test: `tests/test_crawler_workflow.py`

- [ ] **Step 1: Add deterministic log creation**

Ensure the crawler step creates `crawler.log` before running the Python process and keeps `tee` under `pipefail`.

- [ ] **Step 2: Add workflow diagnostics**

Log whether required secrets are set without printing secret values, and emit a short Python/runtime banner before install and crawl work.

- [ ] **Step 3: Make artifact upload non-failing**

Configure the artifact upload step to warn less noisily when the crawler step never generated additional output.

- [ ] **Step 4: Run targeted verification**

Run: `python -m unittest tests.test_crawler_workflow -v`
Expected: PASS

- [ ] **Step 5: Run broader regression check**

Run: `python -m unittest discover -s tests`
Expected: PASS
