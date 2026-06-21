const ANSI = {
  reset: "\x1B[0m",
  yellow: "\x1B[33m",
  red: "\x1B[31m"
};
function shouldColorize() {
  return process.stdout.isTTY !== false;
}
function log(...msgs) {
  {
    console.log(...msgs);
  }
}
function warn(...msgs) {
  {
    if (shouldColorize()) {
      console.warn(ANSI.yellow + msgs.join(" ") + ANSI.reset);
    } else {
      console.warn(...msgs);
    }
  }
}
function error(...msgs) {
  if (shouldColorize()) {
    console.error(ANSI.red + msgs.join(" ") + ANSI.reset);
  } else {
    console.error(...msgs);
  }
}
export {
  error as e,
  log as l,
  warn as w
};
