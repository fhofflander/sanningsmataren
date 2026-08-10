// Generate a bcrypt hash for ADMIN_USERS. Run locally:
//   node scripts/hash-password.mjs
// The password is prompted with echo off and never leaves this process;
// paste only the printed hash into the env var:
//   ADMIN_USERS="jonathan:<hash>,fredrik:<hash>"

import bcrypt from "bcryptjs";
import { createInterface } from "node:readline";

function promptHidden(question) {
  return new Promise((resolve) => {
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    const write = rl._writeToOutput.bind(rl);
    rl.question(question, (answer) => {
      rl.close();
      process.stdout.write("\n");
      resolve(answer);
    });
    rl._writeToOutput = (str) => {
      if (str.includes(question)) write(question);
      else write("*");
    };
  });
}

const password = await promptHidden("Lösenord (skrivs inte ut): ");
if (password.length < 12) {
  console.error("Använd minst 12 tecken.");
  process.exit(1);
}
console.log(bcrypt.hashSync(password, 12));
