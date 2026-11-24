# Mirror and restore

The `mirror` workflow pushes all branches and tags to a second host on every push to `main` and once a day.

**Set up (once, by a maintainer):** create the same repository on the second host (Codeberg or GitLab), make a
token with push access, and add the repository secret `MIRROR_URL` =
`https://<user>:<token>@<host>/<owner>/<repo>.git`.

**Restore** after losing the GitHub repository:

```
git clone --mirror https://<host>/<owner>/<repo>.git
cd <repo>.git
git push --mirror https://github.com/<new owner>/<repo>.git
```

Issues and pull request discussions are not in git. The progress page, task list exports and `results/` are,
which is why the project keeps its state in files where it can.
