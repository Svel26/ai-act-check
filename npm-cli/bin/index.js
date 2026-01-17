#!/usr/bin/env node

import { program } from 'commander';
import inquirer from 'inquirer';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { spawn } from 'child_process';

const CONFIG_DIR = path.join(os.homedir(), '.config', 'ai-act-check');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

program
    .name('annexfour')
    .description('AnnexFour Compliance Scanner Wrapper')
    .version('1.0.0');

// Helper for creating config
async function performLogin() {
    console.log("--- Annexfour Global Login ---");
    console.log("Please paste your API Token (generated in Settings -> Developer).");

    const answers = await inquirer.prompt([
        {
            type: 'password',
            name: 'token',
            message: 'API Token:',
            mask: '*',
            validate: (input) => input.startsWith('anx_') ? true : "Token must start with 'anx_'"
        }
    ]);

    try {
        if (!fs.existsSync(CONFIG_DIR)) {
            fs.mkdirSync(CONFIG_DIR, { recursive: true });
        }
        fs.writeFileSync(CONFIG_FILE, JSON.stringify({ token: answers.token }, null, 2));
        console.log(`\n[+] Success! Token saved to ${CONFIG_FILE}`);
        return answers.token;
    } catch (error) {
        console.error("Error saving config:", error.message);
        process.exit(1);
    }
}

program
    .command('login')
    .description('Authenticate with Annexfour Platform')
    .action(async () => {
        await performLogin();
        console.log("You can now run 'npx @annexfour/cli scan' without arguments.");
    });

program
    .command('scan [path]')
    .description('Run compliance scan on the current or specified directory')
    .option('-t, --token <token>', 'API Token (overrides config)')
    .option('-p, --project-name <name>', 'Project Name')
    .action(async (targetPath, options) => {
        const scanPath = targetPath ? path.resolve(targetPath) : process.cwd();

        // 1. Check for Docker
        try {
            await new Promise((resolve, reject) => {
                const check = spawn('docker', ['--version']);
                check.on('close', (code) => code === 0 ? resolve() : reject());
                check.on('error', reject);
            });
        } catch (e) {
            console.error("Error: Docker is not installed or not running.");
            console.error("Please install Docker to use this tool: https://docs.docker.com/get-docker/");
            process.exit(1);
        }

        // 2. Check Authentication
        let token = options.token;
        if (!token) {
            // Check config file
            if (fs.existsSync(CONFIG_FILE)) {
                // Good, docker will pick it up via mount
            } else {
                console.log("[!] No API Token found. Please authenticate to continue.");
                await performLogin();
                // Token is now saved, docker will pick it up via mount
            }
        }

        // 3. Project Name (Required for authenticated scans)
        const projectName = options.projectName;
        let finalProjectName = projectName;

        if (!finalProjectName) {
            const projectAnswer = await inquirer.prompt([
                {
                    type: 'input',
                    name: 'name',
                    message: 'Project Name:',
                    default: path.basename(scanPath)
                }
            ]);
            finalProjectName = projectAnswer.name;
        }

        // Construct Docker arguments
        const dockerArgs = [
            'run', '--rm', '-i',
            '-v', `${scanPath}:/code`,
            // Mount config read-only so the container picks up the token we just saved
            '-v', `${CONFIG_DIR}:/root/.config/ai-act-check:ro`,
            // Forward Env Vars if present
            process.env.ANNEXFOUR_API_URL ? '-e' : '',
            process.env.ANNEXFOUR_API_URL ? `ANNEXFOUR_API_URL=${process.env.ANNEXFOUR_API_URL}` : '',
            'svenj06/ai-act-check',
            'scan', '/code'
        ].filter(Boolean); // Remove empty strings

        // Pass CLI arguments to container
        if (options.token) {
            dockerArgs.push('--token', options.token);
        }

        // Always pass project name now that we've ensured we have one
        dockerArgs.push('--project-name', finalProjectName);

        console.log(`[*] Launching Scanner via Docker...`);
        // console.log(`DEBUG: docker ${dockerArgs.join(' ')}`);

        const child = spawn('docker', dockerArgs, { stdio: 'inherit' });

        child.on('close', (code) => {
            if (code !== 0) {
                console.log("\n[!] Scan container exited with error.");
            }
            process.exit(code);
        });
    });

program.parse();
