// Import OpenTelemetry configuration
const { tracer, metrics, shutdown } = require('./otel-setup');

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const net = require('net');
const path = require('path');
const fs = require('fs');
const sharp = require('sharp');

// Add stealth plugin to puppeteer
puppeteer.use(StealthPlugin());

// Function to generate a valid directory name based on the URL
function generateParentDirectoryName(url) {
  return `${url.replace(/https?:\/\//, '').replace(/[^\w]/g, '_')}`;
}

// Function to generate a valid directory name based on the flow index
function generateFlowDirectoryName(flowIndex) {
  return `flow_${flowIndex}`;
}

// Function to generate a valid file name based on the page sequence
function generateFileName(index) {
  return `page_${index}.png`;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Function to overlay click position on the image using sharp
async function overlayClickPosition(inputImagePath, outputImagePath, x, y) {
  const marker = Buffer.from(`
    <svg width="20" height="20">
      <circle cx="10" cy="10" r="10" fill="red" />
    </svg>
  `);

  try {
    const tempImagePath = outputImagePath + '_temp.png';

    await sharp(inputImagePath)
      .composite([{ input: marker, left: x - 10, top: y - 10 }])
      .toFile(tempImagePath);

    fs.renameSync(tempImagePath, outputImagePath);
    console.log(`Updated screenshot saved with click overlay at: ${outputImagePath}`);
  } catch (error) {
    console.error('Error overlaying click position on screenshot:', error);
  }
}

// Instrumented classifyScreenshot function
async function classifyScreenshot(screenshotPath) {
  return tracer.startActiveSpan('classifyScreenshot', async (span) => {
    span.setAttribute('screenshot_path', screenshotPath);
    
    const startTime = performance.now();
    
    try {
      const result = await new Promise((resolve, reject) => {
        const classificationHost = '172.17.0.1'; // adjust if necessary
        const classificationPort = 5060; // port where your classification server is running

        const socket = new net.Socket();
        socket.connect(classificationPort, classificationHost, () => {
          console.log(`Connected to classification server for ${screenshotPath}`);
          // Send the screenshot path and then close the connection
          socket.write(`${screenshotPath}\n`, () => {
            socket.end();
            resolve("Sent");
          });
        });
        socket.on('error', (err) => {
          console.error(`Socket error while classifying ${screenshotPath}: ${err}`);
          reject(err);
        });
      });
      
      // Record duration metric
      const endTime = performance.now();
      const durationSeconds = (endTime - startTime) / 1000;
      metrics.classificationDuration.record(durationSeconds, {
        file: path.basename(screenshotPath) 
      });
      
      span.setAttribute('duration_seconds', durationSeconds);
      span.setStatus({ code: 0 }); // OK
      return result;
    } catch (error) {
      span.setStatus({
        code: 1, // ERROR
        message: error.message
      });
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}

// Function to get all select elements and their options
async function getSelectOptions(page) {
  const selectElements = await page.$('select');
  const allSelectOptions = [];

  for (let select of selectElements) {
    const options = await select.evaluate((select) => {
      return Array.from(select.options).map((option) => option.value);
    });
    allSelectOptions.push(options);
  }

  return allSelectOptions;
}

// (Optional) Original function to generate full combinations – not used in the new flow generation logic
function generateOptionCombinations(optionsArray) {
  const combinations = [];

  const helper = (currentCombination, depth) => {
    if (depth === optionsArray.length) {
      combinations.push([...currentCombination]);
      return;
    }
    for (let option of optionsArray[depth]) {
      currentCombination.push(option);
      helper(currentCombination, depth + 1);
      currentCombination.pop();
    }
  };

  helper([], 0);
  return combinations;
}

// Helper: Deduplicate select options and build a mapping.
// For example, if selectOptions is [A, B, A, C], then:
//   - uniqueOptions becomes [A, B, C]
//   - mapping becomes [[0, 2], [1], [3]]
function deduplicateOptionsWithMapping(optionsArray) {
  const uniqueOptions = [];
  const mapping = [];
  const seenKeys = new Map();

  optionsArray.forEach((opts, idx) => {
    const key = JSON.stringify(opts);
    if (seenKeys.has(key)) {
      const uniqueIndex = seenKeys.get(key);
      mapping[uniqueIndex].push(idx);
    } else {
      seenKeys.set(key, uniqueOptions.length);
      uniqueOptions.push(opts);
      mapping.push([idx]);
    }
  });
  return { uniqueOptions, mapping };
}

async function fillInputFields(page) {
  const inputElements = await page.$('input');

  for (let input of inputElements) {
    try {
      await input.evaluate((element) => element.scrollIntoView());
      await sleep(Math.floor(Math.random() * 500) + 500); // Random delay after scrolling

      const isVisible = await input.evaluate((element) => {
        const style = window.getComputedStyle(element);
        return style && style.visibility !== 'hidden' && style.display !== 'none';
      });

      const isReadOnly = await input.evaluate((element) => element.hasAttribute('readonly'));
      const isDisabled = await input.evaluate((element) => element.hasAttribute('disabled'));

      if (isVisible && !isReadOnly && !isDisabled) {
        await Promise.race([
          input.type('aa', { delay: 100 }),
          new Promise((_, reject) => setTimeout(() => reject('Timeout'), 3000)),
        ]);
      }
    } catch (e) {
      // Skipping non-interactable input field.
    }
  }

  await page.evaluate(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  await sleep(Math.floor(Math.random() * 500) + 500); // Random delay after scrolling to top
  await sleep(1000);
}

// Function to detect navigation or new tab
async function detectNavigationOrNewTab(page) {
  const timeout = 5000;
  const browser = page.browser();

  return Promise.race([
    page
      .waitForNavigation({ timeout })
      .then(() => {
        console.log('Navigation detected.');
        return page;
      })
      .catch(() => null),
    new Promise((resolve) => {
      const listener = async (target) => {
        if (target.opener() === page.target()) {
          const newPage = await target.page();
          await newPage.bringToFront();
          console.log('New tab detected.');
          browser.off('targetcreated', listener);
          resolve(newPage);
        }
      };
      browser.on('targetcreated', listener);
      setTimeout(() => {
        browser.off('targetcreated', listener);
        resolve(null);
      }, timeout);
    }),
  ]);
}

// Function to perform the flow for a given combination of select options.
// NOTE: We now pass an additional parameter "mapping" to apply the select values to duplicate selects.
async function performFlow(browser, url, parentDir, client, selectCombination, mapping, flowIndex, clickLimit) {
  // Create a span for the flow
  return tracer.startActiveSpan('performFlow', async (span) => {
    span.setAttribute('url', url);
    span.setAttribute('flow_index', flowIndex);
    
    let page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64)');
    await page.setViewport({ width: 1280, height: 800 });
    await page.evaluateOnNewDocument(() => {
      delete navigator.__proto__.webdriver;
    });
    await page.setDefaultNavigationTimeout(60000);

    try {
      // Instrument page loading with timing
      const pageLoadStartTime = performance.now();
      span.addEvent('navigating_to_url', { url });
      
      await page.goto(url, { timeout: 60000, waitUntil: 'load' });
      
      const pageLoadEndTime = performance.now();
      const pageLoadDuration = (pageLoadEndTime - pageLoadStartTime) / 1000;
      metrics.pageLoadDuration.record(pageLoadDuration, { url: new URL(url).hostname });
      
      span.addEvent('page_loaded', { 
        url, 
        duration_seconds: pageLoadDuration 
      });
      
      await sleep(Math.floor(Math.random() * 2000) + 1000);

      // Retrieve select identifiers (id, name, or fallback index) for all select elements.
      const selectIdentifiers = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('select')).map((el, i) => {
          return { index: i, id: el.id || null, name: el.name || null };
        });
      });

      const actions = [];

      // Check if there are any select options to process.
      if (selectCombination && mapping && mapping.length > 0) {
        // Apply the select options using the deduplicated mapping.
        const selectElements = await page.$('select');
        for (let uniqueIndex = 0; uniqueIndex < mapping.length; uniqueIndex++) {
          const value = selectCombination[uniqueIndex];
          // For every duplicate select element that shares the same option set:
          for (let origIdx of mapping[uniqueIndex]) {
            const selectElement = selectElements[origIdx];
            const selectedValues = await selectElement.select(value);
            if (selectedValues.length === 0) {
              console.error(`Value "${value}" not found in select element at index ${origIdx}.`);
              return;
            }
            console.log(`Set select element at index ${origIdx} to value ${value}`);

            // Wait for any potential navigation
            const newPage = await detectNavigationOrNewTab(page);
            if (newPage && newPage !== page) {
              console.log('Navigation or new tab detected after selecting option.');
              await page.close();
              page = newPage;
              await page.bringToFront();
            }
          }
        }
        const fullSelectMapping = buildFullSelectMapping(mapping, selectCombination, selectIdentifiers);
        actions.push({
          selectOptions: fullSelectMapping
        });
      } else {
        // No select options found: set selectOptions to null in the actions file.
        console.log("No select options to set. Continuing flow without modifying selects.");
        actions.push({
          selectOptions: null
        });
      }
      // Proceed with the rest of the flow.
      await continueFlow(page, url, client, parentDir, flowIndex, 1, 0, clickLimit, selectCombination, actions);
      
      // Record flow completion
      metrics.flowsCompleted.add(1, { 
        url: new URL(url).hostname,
        flow_index: flowIndex 
      });
      
      span.setStatus({ code: 0 }); // OK
    } catch (error) {
      console.error('Error during flow:', error);
      span.setStatus({
        code: 1, // ERROR
        message: error.message
      });
      span.recordException(error);
    } finally {
      if (page && !page.isClosed()) {
        await page.close();
      }
      span.end();
    }
  });
}

function buildFullSelectMapping(mapping, uniqueCombination, selectIdentifiers) {
  // Create an array with the same length as the total number of selects
  const fullMapping = new Array(selectIdentifiers.length);
  // For each unique group, assign the chosen value to every original select in that group.
  mapping.forEach((origIndices, uniqueIndex) => {
    origIndices.forEach((i) => {
      fullMapping[i] = {
        // Use the element's id if available; otherwise name; otherwise fallback to a string using its index.
        identifier: selectIdentifiers[i].id || selectIdentifiers[i].name || `select_${i}`,
        value: uniqueCombination[uniqueIndex]
      };
    });
  });
  return fullMapping;
}

const truncateString = (str, maxLength = 200) => {
  if (str.length > maxLength) {
    return str.slice(0, maxLength) + '...';
  }
  return str;
};

// Function to continue with actions after selecting options
async function continueFlow(page, url, client, parentDir, flowIndex, screenshotIndex, clickCount, clickLimit, selectCombination, actions) {
  return tracer.startActiveSpan('continueFlow', async (span) => {
    span.setAttribute('flow_index', flowIndex);
    span.setAttribute('url', url);
    
    const flowDirName = generateFlowDirectoryName(flowIndex);
    const flowDir = path.join(parentDir, flowDirName);

    await fillInputFields(page);

    // Function to take screenshots
    const takeScreenshot = async () => {
      const screenshotPath = path.join(flowDir, generateFileName(screenshotIndex));
      if (!fs.existsSync(flowDir)) {
        fs.mkdirSync(flowDir, { recursive: true });
      }
      await page.screenshot({ path: screenshotPath });
      console.log(`Screenshot saved to: ${screenshotPath}`);
      metrics.screenshotsTotal.add(1);
      const currentUrl = await page.url();
      screenshotIndex++;
      return { screenshotPath, currentUrl };
    };
    
    console.log('Filled input fields, now taking screenshot');
    let { screenshotPath, currentUrl } = await takeScreenshot();
    console.log('Sending screenshot for classification');
    
    // Call classifyScreenshot with instrumentation (already added in the function)
    classifyScreenshot(screenshotPath)
      .then(() => console.log(`Classification sent for ${screenshotPath}`))
      .catch(err => console.error(`Error sending screenshot ${screenshotPath}: ${err}`));

    let previousElementHTML = null;

    // Main loop to interact with elements based on server response
    while (clickCount < clickLimit) {
      // Instrument click position retrieval
      const clickPositionSpan = tracer.startActiveSpan('getClickPosition', async (clickSpan) => {
        try {
          clickSpan.setAttribute('screenshot_path', screenshotPath);
          clickSpan.setAttribute('flow_index', flowIndex);
          clickSpan.setAttribute('click_count', clickCount);
          
          const startTime = performance.now();
          
          client.write(`${screenshotPath}\n`);

          // Wait for response from the server
          let clickPosition = await new Promise((resolve) => {
            const dataListener = (data) => {
              console.log(`Received from server: ${data}`);
              client.removeListener('data', dataListener); // Clean up listener
              resolve(data.toString().trim());
            };
            client.on('data', dataListener);
          });
          
          // Calculate and record duration
          const endTime = performance.now();
          const durationSeconds = (endTime - startTime) / 1000;
          
          metrics.clickPositionDuration.record(durationSeconds, {
            screenshot: path.basename(screenshotPath)
          });
          
          clickSpan.setAttribute('duration_seconds', durationSeconds);
          clickSpan.setAttribute('response', clickPosition);
          
          // Process the response
          const match = clickPosition.match(/Click Point:\s*(\d+),\s*(\d+)/);
          
          if (clickPosition === 'No login button detected' || clickPosition === 'Error: No relevant element detected.') {
            console.log('No login button detected');
            clickSpan.setAttribute('result', 'no_element_detected');
            return { shouldBreak: true };
          } else if (clickPosition === 'No popups found') {
            console.log('No popups found');
            clickSpan.setAttribute('result', 'no_popups_found');
            return { shouldContinue: true };
          } else if (!match) {
            console.error(`Invalid data received from socket: ${clickPosition}`);
            clickSpan.setStatus({
              code: 1, // ERROR
              message: `Invalid click position: ${clickPosition}`
            });
            throw new Error(`Invalid click position: ${clickPosition}`);
          }
          
          // Valid click position received
          const [x, y] = match.slice(1).map(Number);
          clickSpan.setAttribute('x', x);
          clickSpan.setAttribute('y', y);
          
          return { x, y, shouldProcess: true };
        } catch (error) {
          clickSpan.setStatus({
            code: 1, // ERROR
            message: error.message
          });
          clickSpan.recordException(error);
          throw error;
        } finally {
          clickSpan.end();
        }
      });
      
      // If we need to break the loop
      if (clickPositionSpan.shouldBreak) {
        actions.push({
          step: actions.length,
          clickPosition: null,
          elementHTML: null,
          screenshot: screenshotPath,
          url: currentUrl,
        });
        break;
      }
      
      // If we need to continue to the next iteration
      if (clickPositionSpan.shouldContinue) {
        continue;
      }
      
      // Process the click position if valid
      if (clickPositionSpan.shouldProcess) {
        const { x, y } = clickPositionSpan;
        
        const currentElementHTML = await page.evaluate(({ x, y }) => {
          const element = document.elementFromPoint(x, y);
          return element ? element.outerHTML : null;
        }, { x, y });

        if (currentElementHTML === null || currentElementHTML === previousElementHTML) {
          console.log(currentElementHTML);
          console.log('No element found or repeated element at the click position.');
          actions.push({
            step: actions.length,
            clickPosition: null,
            elementHTML: null,
            screenshot: screenshotPath,
            url: currentUrl,
          });
          break;
        }

        previousElementHTML = currentElementHTML;

        actions.push({
          step: actions.length,
          clickPosition: { x, y },
          elementHTML: truncateString(currentElementHTML),
          screenshot: screenshotPath,
          url: currentUrl,
        });

        await overlayClickPosition(screenshotPath, screenshotPath, x, y);
        console.log(`Clicking at position: (${x}, ${y})`);
        await page.mouse.move(x - 5, y - 5);
        await sleep(Math.floor(Math.random() * 1000) + 500);
        await page.mouse.click(x, y);

        clickCount++;

        // Check for navigation or new tab
        const newPage = await detectNavigationOrNewTab(page);
        if (newPage && newPage !== page) {
          console.log('New tab or navigation detected after click, switching to new page');
          await page.close();
          page = newPage;
          await page.bringToFront();
          await page.setDefaultNavigationTimeout(60000);
        }

        await fillInputFields(page);
        await sleep(4000);
        ({ screenshotPath, currentUrl } = await takeScreenshot());
        
        // Call classifyScreenshot with instrumentation (already added in the function)
        classifyScreenshot(screenshotPath)
          .then(() => console.log(`Classification sent for ${screenshotPath}`))
          .catch(err => console.error(`Error sending screenshot ${screenshotPath}: ${err}`));
      }
    }

    // After the loop, if we've reached the click limit and haven't added a final entry, add one.
    if (clickCount >= clickLimit) {
      actions.push({
        step: actions.length,
        clickPosition: null,
        elementHTML: null,
        screenshot: screenshotPath,
        url: currentUrl,
      });
    }
    // Write actions to JSON file for this specific flow
    const outputJSONPath = path.join(flowDir, `click_actions_flow_${flowIndex}.json`);
    fs.writeFileSync(outputJSONPath, JSON.stringify(actions, null, 2));
    console.log(`Actions saved to: ${outputJSONPath}`);
    
    span.end();
  });
}

// Function to run the crawler
async function runCrawler(url) {
  return tracer.startActiveSpan('runCrawler', async (span) => {
    span.setAttribute('url', url);
    const urlObj = new URL(url);
    span.setAttribute('hostname', urlObj.hostname);
    
    const HOST = '172.17.0.1';
    const PORT = 5000;
    let client;
    let browser;

    try {
      // Start socket connection with retry logic
      client = new net.Socket();

      await new Promise((resolve) => {
        const retryInterval = 1000; // Retry every 1 second

        const tryConnect = () => {
          client.connect(PORT, HOST, () => {
            console.log('Connected to socket server');
            resolve();
          });

          client.on('error', (err) => {
            console.error(`Socket error: ${err.message}`);
            console.log(`Retrying connection in ${retryInterval / 1000} seconds...`);
            setTimeout(tryConnect, retryInterval);
          });
        };

        tryConnect();
      });

      browser = await puppeteer.launch({
        headless: true,
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-gpu',
          '--start-fullscreen',
          '--disable-blink-features=AutomationControlled',
        ],
      });

      const CLICK_LIMIT = 5;

      // Create a parent directory for the URL
      const parentDir = path.join(__dirname, '/screenshot_flows', generateParentDirectoryName(url));
      // Delete the directory if it exists
      if (fs.existsSync(parentDir)) {
        try {
          fs.rmSync(parentDir, { recursive: true, force: true });
        } catch (err) {
          console.warn(`Warning: Unable to remove ${parentDir}: ${err.message}. Continuing...`);
        }
      }
      fs.mkdirSync(parentDir, { recursive: true });

      // Open a page to get the select options
      let page = await browser.newPage();
      await page.goto(url, { waitUntil: 'load' });
      await sleep(Math.floor(Math.random() * 2000) + 1000);

      const selectOptions = await getSelectOptions(page);
      await page.close();

      if (selectOptions.length === 0) {
        console.log("No select options found. Running flow without select options.");
        // Passing null as selectCombination and an empty array for mapping.
        await performFlow(browser, url, parentDir, client, null, [], 0, CLICK_LIMIT);
      } else {
        // Deduplicate select options and build a mapping.
        const { uniqueOptions, mapping } = deduplicateOptionsWithMapping(selectOptions);
        // Define a default combination using the first option from each unique group.
        const defaultCombination = uniqueOptions.map(options => options[0]);

        // Build flows: for each unique select group, try each option (if not the default)
        // while keeping other groups at their default.
        const flows = [];
        uniqueOptions.forEach((options, groupIndex) => {
          options.forEach(option => {
            if (option !== defaultCombination[groupIndex]) {
              const variation = [...defaultCombination];
              variation[groupIndex] = option;
              flows.push(variation);
            }
          });
        });
        console.log(`Generated ${flows.length} flows based on unique select options.`);

        // Iterate over each flow and perform the flow
        for (let i = 0; i < flows.length; i++) {
          const selectCombination = flows[i];
          console.log(`Starting flow ${i} with select options: ${selectCombination}`);
          await performFlow(browser, url, parentDir, client, selectCombination, mapping, i, CLICK_LIMIT);
        }
      }
      
      span.setStatus({ code: 0 }); // OK
    } catch (error) {
      console.error('Error:', error);
      span.setStatus({
        code: 1, // ERROR
        message: error.message
      });
      span.recordException(error);
    } finally {
      if (browser) {
        await browser.close();
        console.log('Browser closed');
      }
      if (client) {
        client.end();
        client.destroy(); // Ensure the socket is fully closed
        console.log('Socket connection closed');
      }
      span.end();
    }
  });
}

// Function to read URLs from the file and add "http://" if not present
function getUrlsFromFile(filePath) {
  try {
    const urls = fs
      .readFileSync(filePath, 'utf-8')
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((url) => (url.startsWith('http://') || url.startsWith('https://') ? url : `http://${url}`));
    return urls;
  } catch (error) {
    console.error(`Error reading file: ${error.message}`);
    return [];
  }
}

async function main() {
  // Process signal for graceful shutdown
  process.on('SIGTERM', async () => {
    console.log('SIGTERM received, shutting down gracefully');
    try {
      await shutdown();
      console.log('OpenTelemetry shut down successfully');
    } catch (error) {
      console.error('Error shutting down OpenTelemetry:', error);
    }
    process.exit(0);
  });
  
  process.on('SIGINT', async () => {
    console.log('SIGINT received, shutting down gracefully');
    try {
      await shutdown();
      console.log('OpenTelemetry shut down successfully');
    } catch (error) {
      console.error('Error shutting down OpenTelemetry:', error);
    }
    process.exit(0);
  });

  const args = process.argv.slice(2); // Get arguments passed to the script
  let url = args[0]; // Take the first argument as the URL

  if (!url.startsWith('http')) {
    url = 'http://' + url;
  }

  if (url) {
    console.log(`Processing single URL from arguments: ${url}`);
    try {
      await runCrawler(url); // Call the crawler for the given URL
    } catch (error) {
      console.error(`Error processing URL ${url}: ${error.message}`);
    }
  } else {
    console.log('Invalid URL passed in');
  }

  console.log('Finished processing all URLs.');
  
  // Shutdown OpenTelemetry before exiting
  try {
    await shutdown();
    console.log('OpenTelemetry shut down successfully');
  } catch (error) {
    console.error('Error shutting down OpenTelemetry:', error);
  }
  
  process.exit(0);
}

main().catch(error => {
  console.error('Unhandled error in main:', error);
  process.exit(1);
});