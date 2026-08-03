"""git add/commit/push wrapper for docs/. No-ops if nothing changed."""

import subprocess


def publish(repo_dir, generated_at_str):
    subprocess.run(["git", "add", "docs/"], cwd=repo_dir, check=True)

    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=repo_dir
    )
    if diff.returncode == 0:
        print("No changes to publish.")
        return False

    subprocess.run(
        ["git", "commit", "-m", f"Update standings: {generated_at_str}"],
        cwd=repo_dir,
        check=True,
    )
    subprocess.run(["git", "push"], cwd=repo_dir, check=True)
    print("Published.")
    return True
