#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

const playwright = require("playwright");
const { StdioServerTransport } = require("playwright-core/lib/mcpBundle");
const officialPackage = require("@playwright/mcp/package.json");

const playwrightRoot = path.dirname(require.resolve("playwright/package.json"));
const { BrowserServerBackend } = require(path.join(
  playwrightRoot,
  "lib",
  "mcp",
  "browser",
  "browserServerBackend.js",
));
const { resolveConfig } = require(path.join(
  playwrightRoot,
  "lib",
  "mcp",
  "browser",
  "config.js",
));
const { createServer } = require(path.join(
  playwrightRoot,
  "lib",
  "mcp",
  "sdk",
  "server.js",
));


function parseArgs(argv) {
  const args = argv.slice(2);
  if (args.includes("--help") || args.includes("-h")) {
    printHelp();
    process.exit(0);
  }

  const configIndex = args.indexOf("--config");
  if (configIndex === -1 || !args[configIndex + 1]) {
    throw new Error("Missing required --config <path> argument.");
  }

  return {
    configPath: args[configIndex + 1],
  };
}


function printHelp() {
  process.stdout.write(
    [
      "Local Playwright MCP wrapper",
      "",
      "Usage:",
      "  node server.js --config <config-path>",
      "",
      "This wrapper keeps the official Playwright MCP toolset",
      "and adds local headed/headless config selection plus",
      "storage-state sync before close for headed mode.",
      "",
    ].join("\n"),
  );
}


function loadAppConfig(configPath) {
  const absolutePath = path.resolve(process.cwd(), configPath);
  const raw = fs.readFileSync(absolutePath, "utf-8");
  const parsed = JSON.parse(raw);
  return {
    appConfig: parsed,
    absolutePath,
    baseDir: path.dirname(absolutePath),
  };
}


function resolveMaybeRelative(baseDir, value) {
  if (!value || typeof value !== "string") {
    return value;
  }
  return path.isAbsolute(value) ? value : path.resolve(baseDir, value);
}


function normalizeConfigForOfficial(appConfig, baseDir) {
  const officialConfig = JSON.parse(JSON.stringify(appConfig));
  delete officialConfig.mode;
  delete officialConfig.sync;

  if (officialConfig.browser?.userDataDir) {
    officialConfig.browser.userDataDir = resolveMaybeRelative(baseDir, officialConfig.browser.userDataDir);
  }

  const storageState = officialConfig.browser?.contextOptions?.storageState;
  if (storageState) {
    const resolvedStorageState = resolveMaybeRelative(baseDir, storageState);
    if (fs.existsSync(resolvedStorageState)) {
      officialConfig.browser.contextOptions.storageState = resolvedStorageState;
    } else {
      delete officialConfig.browser.contextOptions.storageState;
      process.stderr.write(
        `[playwright-wrapper] storage state not found yet, starting without it: ${resolvedStorageState}\n`,
      );
    }
  }

  return officialConfig;
}


function resolveBrowserType(browserName) {
  const browserType = playwright[browserName];
  if (!browserType) {
    throw new Error(`Unsupported browserName: ${browserName}`);
  }
  return browserType;
}


function ensureParentDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}


async function createManagedContextFactory(resolvedConfig, appConfig, baseDir) {
  const browserType = resolveBrowserType(resolvedConfig.browser.browserName);
  const syncEnabled = appConfig.mode === "headed" && appConfig.sync?.enabled === true;
  const syncTrigger = appConfig.sync?.trigger;
  const sharedStatePath = resolveMaybeRelative(baseDir, appConfig.sync?.storageStatePath);

  return {
    name: "persistent-or-shared",
    description: "Create a browser context with local profile/storage-state management",
    async createContext() {
      if (appConfig.mode === "headed") {
        const userDataDir = resolvedConfig.browser.userDataDir;
        fs.mkdirSync(userDataDir, { recursive: true });

        const browserContext = await browserType.launchPersistentContext(userDataDir, {
          ...resolvedConfig.browser.launchOptions,
          ...resolvedConfig.browser.contextOptions,
          handleSIGINT: false,
          handleSIGTERM: false,
          ignoreDefaultArgs: ["--disable-extensions"],
          assistantMode: true,
        });

        return {
          browserContext,
          close: async () => {
            if (syncEnabled && syncTrigger === "before_close" && sharedStatePath) {
              ensureParentDir(sharedStatePath);
              await browserContext.storageState({ path: sharedStatePath });
            }
            await browserContext.close();
          },
        };
      }

      const browser = await browserType.launch({
        ...resolvedConfig.browser.launchOptions,
        handleSIGINT: false,
        handleSIGTERM: false,
      });

      const browserContext = await browser.newContext({
        ...resolvedConfig.browser.contextOptions,
      });

      return {
        browserContext,
        close: async () => {
          await browserContext.close();
          await browser.close();
        },
      };
    },
  };
}


async function main() {
  const { configPath } = parseArgs(process.argv);
  const { appConfig, baseDir } = loadAppConfig(configPath);
  const officialLikeConfig = normalizeConfigForOfficial(appConfig, baseDir);
  const resolvedConfig = await resolveConfig(officialLikeConfig);
  const factory = await createManagedContextFactory(resolvedConfig, appConfig, baseDir);

  const server = createServer(
    "Playwright",
    officialPackage.version,
    new BrowserServerBackend(resolvedConfig, factory),
    false,
  );

  await server.connect(new StdioServerTransport());
}


main().catch((error) => {
  process.stderr.write(`${error.stack || String(error)}\n`);
  process.exit(1);
});
