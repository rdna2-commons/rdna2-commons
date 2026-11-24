# Title runs

How far the engine gets on a real title, reported without naming or sharing anything from it.

**State today:** no build is registered in `builds/` yet, so reports go in as `unregistered` until a maintainer registers the first build from two matching hashes. The build profile `tools/local_run.py --profile` needs, for the title the engine was developed against, is the Leonida continuation (github.com/ubiquitarianism/leonida): clone it and pass its folder.

1. **Builds are hashes.** `builds/<id>.json` registers a build by the SHA-256 and size of its executable, under a
   neutral id. A maintainer adds a build after two people have confirmed the hash from their own copies.
2. **Check your copy:** `python3 -I tools/check_build.py <your install dir> <list>` with a one-line list
   `<exe_sha256>  <exe name>`. Report only on a build that matches.
3. **Run it with one command**, on your own machine:

   ```
   python3 -I tools/local_run.py --profile <checkout with the title's build profile> --game <your copy> --work <folder>
   ```

   It builds your copy with this repository's engine, runs it with the trace and the crash report on, and writes
   `<folder>/report/<login>.json` from an allow-list: the stage reached (up to first-frame it is detected; pass
   `--stage-reached` for menu, in-world or playable), fps, where it stopped as module+offset, and shader counts by
   failure reason. Read it before sending it.
4. **Report:** add `title-runs/<build id>/<engine commit>/<your login>.json` in a pull request (format in
   `tools/title_runs.py`): the furthest **stage**, fps, where it **stopped** (`module+0xOFFSET reason`), and short
   notes. The bot rejects a report not named after its author.
5. **Confirmation:** a stage counts for a (build, commit) once two different people report reaching it or further.
   The progress page shows the furthest confirmed stage per build.

Stages, in order: `loads`, `imports-resolved`, `device-created`, `first-frame`, `menu`, `in-world`, `playable`.

**Never in a report:** screenshots, video, audio, logs that quote the title's code or data, dumps, shader
listings, file contents, or where to get a title. An offset and a one-line reason are enough to find a problem
in your own copy.

**Profiles** that turn your own copy into a build the engine can run (file lists, build stages) are maintained
outside this repository; see engine/README.md.
