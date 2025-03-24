const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const net = require('net');
const path = require('path');
const fs = require('fs');
const sharp = require('sharp');

// Import OpenTelemetry
const { sdk } = require('./otel-setup');
const { trace, metrics, context } = require('@opentelemetry/api');

// Create tracer and meters
const tracer = trace.getTracer('crawler-tracer');
const meter = metrics.getMeter('crawler-metrics');

// Create metrics
const pageLoadHistogram = meter.createHistogram('page_load_duration', {
  description: 'Duration of page loads in milliseconds',
  unit: 'ms',
});

const screenshotClassificationHistogram = meter.createHistogram('screenshot_classification_duration', {
  description: 'Duration of screenshot classification in milliseconds',
  unit: 'ms',
});

const clickPositionRetrievalHistogram = meter.createHistogram('click_position_retrieval_duration', {
  description: 'Duration of retrieving click positions in milliseconds',
  unit: 'ms',
});

const flowDurationHistogram = meter.createHistogram('flow_duration', {
  description: 'Duration of a complete flow in milliseconds',
  unit: 'ms',
});

const crawlDurationHistogram = meter.createHistogram('total_crawl_duration', {
  description: 'Duration of the entire crawl in milliseconds',
  unit: 'ms',
});

const clickCounter = meter.createCounter('total_clicks', {
  description: 'Total number of clicks performed',
});

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
  return tracer.startActiveSpan('overlayClickPosition', async (span) => {
    const marker = Buffer.from(`
      <svg width="20" height="20">
        <circle cx="10" cy="10" r="10" fill="red" />
      </svg>
    `);

    try {
      span.setAttribute('input_path', inputImagePath);
      span.setAttribute('output_path', outputImagePath);
      span.setAttribute('click_x', x);
      span.setAttribute('click_y', y);
      
      const tempImagePath = outputImagePath + '_temp.png';

      await sharp(inputImagePath)
        .composite([{ input: marker, left: x - 10, top: y - 10 }])
        .toFile(tempImagePath);

      fs.renameSync(tempImagePath, outputImagePath);
      console.log(`Updated screenshot saved with click overlay at: ${outputImagePath}`);
      
      span.setAttribute('success', true);
    } catch (error) {
      console.error('Error overlaying click position on screenshot:', error);
      span.recordException(error);
      span.setAttribute('success', false);
    } finally {
      span.end();
    }
  });
}

async function classifyScreenshot(screenshotPath) {
  const span = tracer.startSpan('classifyScreenshot');
  span.setAttribute('screenshot_path', screenshotPath);
  
  const startTime = Date.now();
  
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
        span.recordException(err);
        reject(err);
      });
    });
    
    const duration = Date.now() - startTime;
    screenshotClassificationHistogram.record(duration);
    span.setAttribute('duration_ms', duration);
    
    return result;
  } catch (error) {
    span.recordException(error);
    throw error;
  } finally {
    span.end();
  }
}

// Function to get all select elements and their options
async function getSelectOptions(page) {
  return tracer.startActiveSpan('getSelectOptions', async (span) => {
    try {
      const selectElements = await page.$$('select');
      const allSelectOptions = [];

      for (let select of selectElements) {
        const options = await select.evaluate((select) => {
          return Array.from(select.options).map((option) => option.value);
        });
        allSelectOptions.push(options);
      }

      span.setAttribute('select_count', selectElements.length);
      span.setAttribute('option_count', allSelectOptions.reduce((sum, opts) => sum + opts.length, 0));
      return allSelectOptions;
    } catch (error) {
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}

// (Optional) Original function to generate full combinations – not used in the new flow generation logic
function generateOptionCombinations(optionsArray) {
  return tracer.startActiveSpan('generateOptionCombinations', (span) => {
    try {
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
      
      span.setAttribute('combination_count', combinations.length);
      return combinations;
    } catch (error) {
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}

// Helper: Deduplicate select options and build a mapping.
// For example, if selectOptions is [A, B, A, C], then:
//   - uniqueOptions becomes [A, B, C]
//   - mapping becomes [[0, 2], [1], [3]]
function deduplicateOptionsWithMapping(optionsArray) {
  return tracer.startActiveSpan('deduplicateOptionsWithMapping', (span) => {
    try {
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
      
      span.setAttribute('unique_option_groups', uniqueOptions.length);
      span.setAttribute('total_options', optionsArray.length);
      
      return { uniqueOptions, mapping };
    } catch (error) {
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}

async function fillInputFields(page) {
  return tracer.startActiveSpan('fillInputFields', async (span) => {
    try {
      const inputElements = await page.$$('input');
      let filledCount = 0;

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
            filledCount++;
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
      
      span.setAttribute('total_input_elements', inputElements.length);
      span.setAttribute('filled_input_elements', filledCount);
      
    } catch (error) {
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}

// Function to detect navigation or new tab
async function detectNavigationOrNewTab(page) {
  const span = tracer.startSpan('detectNavigationOrNewTab');
  const timeout = 5000;
  const browser = page.browser();
  
  try {
    const result = await Promise.race([
      page
        .waitForNavigation({ timeout })
        .then(() => {
          console.log('Navigation detected.');
          span.setAttribute('navigation_type', 'same_page');
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
            span.setAttribute('navigation_type', 'new_tab');
            resolve(newPage);
          }
        };
        browser.on('targetcreated', listener);
        setTimeout(() => {
          browser.off('targetcreated', listener);
          span.setAttribute('navigation_type', 'none');
          resolve(null);
        }, timeout);
      }),
    ]);
    
    return result;
  } catch (error) {
    span.recordException(error);
    throw error;
  } finally {
    span.end();
  }
}

// Function to perform the flow for a given combination of select options.
// NOTE: We now pass an additional parameter "mapping" to apply the select values to duplicate selects.
async function performFlow(browser, url, parentDir, client, selectCombination, mapping, flowIndex, clickLimit) {
  return tracer.startActiveSpan(`performFlow_${flowIndex}`, async (span) => {
    const flowStartTime = Date.now();
    let page = null;
    
    try {
      page = await browser.newPage();
      await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64)');
      await page.setViewport({ width: 1280, height: 800 });
      await page.evaluateOnNewDocument(() => {
        delete navigator.__proto__.webdriver;
      });
      await page.setDefaultNavigationTimeout(60000);

      span.setAttribute('flow_index', flowIndex);
      span.setAttribute('url', url);
      span.setAttribute('click_limit', clickLimit);
      span.setAttribute('has_select_combination', !!selectCombination);

      // Start page load trace
      const pageLoadStartTime = Date.now();
      await tracer.startActiveSpan('page_load', async (pageLoadSpan) => {
        try {
          await page.goto(url, { timeout: 60000, waitUntil: 'load' });
          const pageLoadDuration = Date.now() - pageLoadStartTime;
          pageLoadHistogram.record(pageLoadDuration);
          pageLoadSpan.setAttribute('duration_ms', pageLoadDuration);
          pageLoadSpan.setAttribute('url', url);
        } catch (error) {
          pageLoadSpan.recordException(error);
          throw error;
        } finally {
          pageLoadSpan.end();
        }
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
        await tracer.startActiveSpan('apply_select_options', async (selectSpan) => {
          try {
            // Apply the select options using the deduplicated mapping.
            const selectElements = await page.$$('select');
            selectSpan.setAttribute('select_elements_count', selectElements.length);
            selectSpan.setAttribute('mapping_length', mapping.length);
            
            for (let uniqueIndex = 0; uniqueIndex < mapping.length; uniqueIndex++) {
              const value = selectCombination[uniqueIndex];
              // For every duplicate select element that shares the same option set:
              for (let origIdx of mapping[uniqueIndex]) {
                const selectElement = selectElements[origIdx];
                const selectedValues = await selectElement.select(value);
                if (selectedValues.length === 0) {
                  console.error(`Value "${value}" not found in select element at index ${origIdx}.`);
                  selectSpan.setAttribute('error', `Value "${value}" not found in select element at index ${origIdx}`);
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
                  selectSpan.setAttribute('navigation_after_select', true);
                }
              }
            }
            
            const fullSelectMapping = buildFullSelectMapping(mapping, selectCombination, selectIdentifiers);
            actions.push({
              selectOptions: fullSelectMapping
            });
          } catch (error) {
            selectSpan.recordException(error);
            throw error;
          } finally {
            selectSpan.end();
          }
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
      
    } catch (error) {
      console.error('Error during flow:', error);
      span.recordException(error);
    } finally {
      if (page && !page.isClosed()) {
        await page.close();
      }
      
      const flowDuration = Date.now() - flowStartTime;
      flowDurationHistogram.record(flowDuration);
      span.setAttribute('duration_ms', flowDuration);
      span.end();
    }
  });
}

function buildFullSelectMapping(mapping, uniqueCombination, selectIdentifiers) {
  return tracer.startActiveSpan('buildFullSelectMapping', (span) => {
    try {
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
      
      span.setAttribute('mapping_entries', fullMapping.length);
      return fullMapping;
    } catch (error) {
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}


const truncateString = (str, maxLength = 200) => {
  if (str.length > maxLength) {
    return str.slice(0, maxLength) + '...';
  }
  return str;
};

// This is the specific section with the fix for the infinite loop

async function continueFlow(page, url, client, parentDir, flowIndex, screenshotIndex, clickCount, clickLimit, selectCombination, actions) {
  const span = tracer.startSpan(`continueFlow_${flowIndex}`);
  span.setAttribute('flow_index', flowIndex);
  span.setAttribute('initial_click_count', clickCount);
  span.setAttribute('click_limit', clickLimit);
  
  try {
    const flowDirName = generateFlowDirectoryName(flowIndex);
    const flowDir = path.join(parentDir, flowDirName);

    await fillInputFields(page);

    // Function to take screenshots
    const takeScreenshot = async () => {
      const screenshotSpan = tracer.startSpan('takeScreenshot');
      screenshotSpan.setAttribute('screenshot_index', screenshotIndex);
      
      try {
        const screenshotPath = path.join(flowDir, generateFileName(screenshotIndex));
        screenshotSpan.setAttribute('screenshot_path', screenshotPath);
        
        if (!fs.existsSync(flowDir)) {
          fs.mkdirSync(flowDir, { recursive: true });
        }
        await page.screenshot({ path: screenshotPath });
        console.log(`Screenshot saved to: ${screenshotPath}`);
        const currentUrl = await page.url();
        screenshotIndex++;
        return { screenshotPath, currentUrl };
      } catch (error) {
        screenshotSpan.recordException(error);
        throw error;
      } finally {
        screenshotSpan.end();
      }
    };
    
    console.log('Filled input fields, now taking screenshot');
    let { screenshotPath, currentUrl } = await takeScreenshot();
    console.log('Sending screenshot for classification');
    
    classifyScreenshot(screenshotPath)
      .then(() => console.log(`Classification sent for ${screenshotPath}`))
      .catch(err => console.error(`Error sending screenshot ${screenshotPath}: ${err}`));

    // Track previously clicked positions to avoid infinite loops
    const clickedPositions = new Set();
    let previousElementHTML = null;

    // Main loop to interact with elements based on server response
    while (clickCount < clickLimit) {
      const clickSpan = tracer.startSpan(`click_interaction_${clickCount}`);
      clickSpan.setAttribute('click_number', clickCount);
      clickSpan.setAttribute('current_url', currentUrl);
      
      try {
        // Get click position from server
        const clickPositionStartTime = Date.now();
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
        
        const clickPositionDuration = Date.now() - clickPositionStartTime;
        clickPositionRetrievalHistogram.record(clickPositionDuration);
        clickSpan.setAttribute('click_position_retrieval_ms', clickPositionDuration);
        clickSpan.setAttribute('click_position_response', clickPosition);

        const match = clickPosition.match(/Click Point:\s*(\d+),\s*(\d+)/);
        if (clickPosition === 'No login button detected' || clickPosition === 'Error: No relevant element detected.') {
          console.log('No login button detected');
          clickSpan.setAttribute('result', 'no_login_button');
          actions.push({
            step: actions.length,
            clickPosition: null,
            elementHTML: null,
            screenshot: screenshotPath,
            url: currentUrl,
          });
          // End the span before breaking
          clickSpan.end();
          break; // Exit the loop
        } else if (clickPosition === 'No popups found') {
          console.log('No popups found');
          clickSpan.setAttribute('result', 'no_popups');
          // End the span before breaking
          clickSpan.end();
          break; // Exit the loop
        } else if (!match) {
          console.error(`Invalid data received from socket: ${clickPosition}`);
          clickSpan.setAttribute('result', 'invalid_data');
          clickSpan.recordException(new Error(`Invalid click position: ${clickPosition}`));
          // End the span before breaking
          clickSpan.end();
          break; // Exit the loop
        }

        const [x, y] = match.slice(1).map(Number);
        const positionKey = `${x},${y}`;
        
        // Check if we've already clicked this position
        if (clickedPositions.has(positionKey)) {
          console.log(`Already clicked at position (${x}, ${y}). Skipping to avoid infinite loop.`);
          clickSpan.setAttribute('result', 'repeated_click_position');
          // End the span before breaking
          clickSpan.end();
          break; // Exit the loop to avoid infinite loop
        }
        
        // Add this position to our clicked positions set
        clickedPositions.add(positionKey);
        
        clickSpan.setAttribute('click_x', x);
        clickSpan.setAttribute('click_y', y);

        const currentElementHTML = await page.evaluate(({ x, y }) => {
          const element = document.elementFromPoint(x, y);
          return element ? element.outerHTML : null;
        }, { x, y });

        if (currentElementHTML === null) {
          console.log('No element found at the click position.');
          clickSpan.setAttribute('result', 'no_element');
          actions.push({
            step: actions.length,
            clickPosition: null,
            elementHTML: null,
            screenshot: screenshotPath,
            url: currentUrl,
          });
          // End the span before breaking
          clickSpan.end();
          break; // Exit the loop
        }

        // Log element found at position for debugging
        console.log(`Element at position (${x}, ${y}): ${currentElementHTML.slice(0, 100)}...`);
        
        // We continue even if it's the same element, we just log it
        if (currentElementHTML === previousElementHTML) {
          console.log('Warning: Same element as previous click. Continuing anyway.');
          clickSpan.setAttribute('same_as_previous', true);
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
        clickCounter.add(1);

        clickCount++;

        // Check for navigation or new tab
        const newPage = await detectNavigationOrNewTab(page);
        if (newPage && newPage !== page) {
          console.log('New tab or navigation detected after click, switching to new page');
          await page.close();
          page = newPage;
          await page.bringToFront();
          await page.setDefaultNavigationTimeout(60000);
          clickSpan.setAttribute('navigation_after_click', true);
        }

        await fillInputFields(page);
        await sleep(4000);
        ({ screenshotPath, currentUrl } = await takeScreenshot());
        
        // Use promise chaining instead of await to avoid blocking
        classifyScreenshot(screenshotPath)
          .then(() => console.log(`Classification sent for ${screenshotPath}`))
          .catch(err => console.error(`Error sending screenshot ${screenshotPath}: ${err}`));
          
        clickSpan.setAttribute('result', 'success');
        // End the span at the end of successful iteration
        clickSpan.end();
      } catch (error) {
        // Only record exception and end span if it hasn't been ended already
        try {
          clickSpan.recordException(error);
          clickSpan.end();
        } catch (spanError) {
          // If we get an error ending the span, it was likely already ended
          console.log(`Note: Span may have already been ended: ${spanError.message}`);
        }
        break; // Exit the loop on error
      }
      // Removed the clickSpan.end() from the finally block to prevent double-ending
    }

    // After the loop, if we've reached the click limit and haven't added a final entry, add one.
    if (clickCount >= clickLimit || actions[actions.length - 1].clickPosition !== null) {
      actions.push({
        step: actions.length,
        clickPosition: null,
        elementHTML: null,
        screenshot: screenshotPath,
        url: currentUrl,
      });
    }
    
    // Write actions to JSON file for this specific flow
    const writeSpan = tracer.startSpan('write_actions_json');
    writeSpan.setAttribute('flow_index', flowIndex);
    
    try {
      const outputJSONPath = path.join(flowDir, `click_actions_flow_${flowIndex}.json`);
      writeSpan.setAttribute('json_path', outputJSONPath);
      writeSpan.setAttribute('actions_count', actions.length);
      
      fs.writeFileSync(outputJSONPath, JSON.stringify(actions, null, 2));
      console.log(`Actions saved to: ${outputJSONPath}`);
    } catch (error) {
      writeSpan.recordException(error);
      throw error;
    } finally {
      writeSpan.end();
    }
    
    span.setAttribute('total_clicks', clickCount);
    span.setAttribute('actions_recorded', actions.length);
    
  } catch (error) {
    span.recordException(error);
    throw error;
  } finally {
    span.end();
  }
}

async function connectSocketWithRetry(host, port) {
  const span = tracer.startSpan('socket_connection');
  span.setAttribute('host', host);
  span.setAttribute('port', port);
  
  const client = new net.Socket();
  let retryCount = 0;
  
  try {
    await new Promise((resolve, reject) => {
      const retryInterval = 1000; // Retry every 1 second
      let timeout;

      const handleError = (err) => {
        console.error(`Socket error: ${err.message}`);
        console.log(`Retrying connection in ${retryInterval / 1000} seconds...`);
        span.setAttribute('last_error', err.message);
        clearTimeout(timeout);
        timeout = setTimeout(tryConnect, retryInterval);
      };

      const tryConnect = () => {
        retryCount++;
        span.setAttribute('retry_count', retryCount);
        
        client.once('error', handleError);
        
        client.connect(port, host, () => {
          client.removeListener('error', handleError);
          console.log('Connected to socket server');
          span.setAttribute('connected', true);
          resolve();
        });
      };

      tryConnect();
    });
    
    return client;
  } catch (error) {
    span.recordException(error);
    throw error;
  } finally {
    span.end();
  }
}

// Function to run the crawler
async function runCrawler(url) {
  const span = tracer.startSpan('runCrawler');
  span.setAttribute('url', url);
  
  const crawlStartTime = Date.now();
  const HOST = '172.17.0.1';
  const PORT = 5000;
  let client;
  let browser;

  try {
    // Start socket connection with retry logic
    client = await connectSocketWithRetry(HOST, PORT);

    // Launch browser
    const browserSpan = tracer.startSpan('browser_launch');
    try {
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
      browserSpan.setAttribute('success', true);
    } catch (error) {
      browserSpan.recordException(error);
      throw error;
    } finally {
      browserSpan.end();
    }

    const CLICK_LIMIT = 5;
    span.setAttribute('click_limit', CLICK_LIMIT);

    // Create a parent directory for the URL
    const parentDir = path.join(__dirname, '/screenshot_flows', generateParentDirectoryName(url));
    span.setAttribute('parent_dir', parentDir);
    
    // Delete the directory if it exists
    if (fs.existsSync(parentDir)) {
      try {
        fs.rmSync(parentDir, { recursive: true, force: true });
      } catch (err) {
        console.warn(`Warning: Unable to remove ${parentDir}: ${err.message}. Continuing...`);
        span.setAttribute('directory_removal_warning', err.message);
      }
    }
    fs.mkdirSync(parentDir, { recursive: true });

    // Open a page to get the select options
    let selectOptions = [];
    const selectSpan = tracer.startSpan('get_initial_select_options');
    try {
      let page = await browser.newPage();
      await page.goto(url, { waitUntil: 'load' });
      await sleep(Math.floor(Math.random() * 2000) + 1000);

      selectOptions = await getSelectOptions(page);
      selectSpan.setAttribute('select_options_count', selectOptions.length);
      await page.close();
    } catch (error) {
      selectSpan.recordException(error);
      throw error;
    } finally {
      selectSpan.end();
    }

    if (selectOptions.length === 0) {
      console.log("No select options found. Running flow without select options.");
      span.setAttribute('has_select_options', false);
      // Passing null as selectCombination and an empty array for mapping.
      await performFlow(browser, url, parentDir, client, null, [], 0, CLICK_LIMIT);
    } else {
      span.setAttribute('has_select_options', true);
      
      // Deduplicate select options and build a mapping.
      const { uniqueOptions, mapping } = deduplicateOptionsWithMapping(selectOptions);
      span.setAttribute('unique_option_groups', uniqueOptions.length);
      
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
      span.setAttribute('total_flows', flows.length);

      // Iterate over each flow and perform the flow
      for (let i = 0; i < flows.length; i++) {
        const selectCombination = flows[i];
        console.log(`Starting flow ${i} with select options: ${selectCombination}`);
        await performFlow(browser, url, parentDir, client, selectCombination, mapping, i, CLICK_LIMIT);
      }
    }
  } catch (error) {
    console.error('Error:', error);
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
    
    const crawlDuration = Date.now() - crawlStartTime;
    crawlDurationHistogram.record(crawlDuration);
    span.setAttribute('duration_ms', crawlDuration);
    span.end();
  }
}

// Function to read URLs from the file and add "http://" if not present
function getUrlsFromFile(filePath) {
  return tracer.startActiveSpan('getUrlsFromFile', (span) => {
    try {
      span.setAttribute('file_path', filePath);
      
      const urls = fs
        .readFileSync(filePath, 'utf-8')
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0)
        .map((url) => (url.startsWith('http://') || url.startsWith('https://') ? url : `http://${url}`));
      
      span.setAttribute('url_count', urls.length);
      return urls;
    } catch (error) {
      console.error(`Error reading file: ${error.message}`);
      span.recordException(error);
      return [];
    } finally {
      span.end();
    }
  });
}

async function main() {
  const mainSpan = tracer.startSpan('main');
  
  try {
    const args = process.argv.slice(2); // Get arguments passed to the script
    let url = args[0]; // Take the first argument as the URL

    if (!url) {
      console.log('Invalid URL passed in');
      mainSpan.setAttribute('error', 'invalid_url');
      return;
    }

    if (!url.startsWith('http')) {
      url = 'http://' + url;
    }

    mainSpan.setAttribute('target_url', url);
    console.log(`Processing single URL from arguments: ${url}`);
    
    try {
      await runCrawler(url); // Call the crawler for the given URL
    } catch (error) {
      console.error(`Error processing URL ${url}: ${error.message}`);
      mainSpan.recordException(error);
    }

    console.log('Finished processing all URLs.');
  } catch (error) {
    mainSpan.recordException(error);
    console.error('Unexpected error in main function:', error);
  } finally {
    mainSpan.end();
    // Shutdown the OpenTelemetry SDK to flush any remaining spans
    await sdk.shutdown();
    process.exit(0);
  }
}

// Entry point
main().catch(err => {
  console.error('Fatal error:', err);
  sdk.shutdown().finally(() => process.exit(1));
});

// runCrawler('www.cadencebank.com')
/**
 * www.ucbi.com
 * www.22ndstatebank.com  
 */