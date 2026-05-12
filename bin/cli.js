#!/usr/bin/env node

/**
 * Thin Node.js wrapper so `npx stata-cli` works.
 *
 * Tries, in order:
 *   1. uvx  stata-cli   (fast, isolated)
 *   2. pipx run stata-cli
 *   3. python3 -m stata_cli  (assumes pip-installed)
 */

const { execFileSync } = require("child_process");
const args = process.argv.slice(2);

const runners = [
  { cmd: "uvx",     argv: ["stata-cli", ...args] },
  { cmd: "pipx",    argv: ["run", "stata-cli", ...args] },
  { cmd: "python3", argv: ["-m", "stata_cli", ...args] },
  { cmd: "python",  argv: ["-m", "stata_cli", ...args] },
];

for (const { cmd, argv } of runners) {
  try {
    execFileSync(cmd, argv, { stdio: "inherit" });
    process.exit(0);
  } catch (err) {
    if (err.status != null) {
      // The child ran but exited non-zero – propagate its exit code.
      process.exit(err.status);
    }
    // Command not found – try the next runner.
  }
}

console.error(
  "stata-cli: could not find a Python environment.\n" +
  "Install one of: uv (https://github.com/astral-sh/uv), " +
  "pipx (https://pypa.github.io/pipx/), or Python 3.10+."
);
process.exit(1);
