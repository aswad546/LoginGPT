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
  return tracer.startActiveSpan('classifyScreenshot', async (span) => {
    span.setAttribute('screenshot_path', screenshotPath);
    const startTime = Date.now();
    let socket = null;
    
    try {
      const result = await new Promise((resolve, reject) => {
        const classificationHost = '172.17.0.1'; // adjust if necessary
        const classificationPort = 5060; // port where your classification server is running
        
        socket = new net.Socket();
        
        // Add handler to receive the response data
        socket.on('data', (data) => {
          const response = data.toString().trim();
          console.log(`Received classification response for ${screenshotPath}: ${response}`);
          span.setAttribute('classification_result', response);
          
          // Close the socket now that we have the response
          socket.end();
          
          // Resolve with the actual response
          resolve(response);
        });
        
        socket.on('error', (err) => {
          console.error(`Socket error while classifying ${screenshotPath}: ${err}`);
          span.recordException(err);
          reject(err);
        });
        
        // Add timeout to prevent hanging indefinitely
        socket.setTimeout(30000, () => {
          console.warn(`Classification timeout for ${screenshotPath}`);
          span.setAttribute('timeout', true);
          socket.destroy();
          reject(new Error("Classification request timed out"));
        });
        
        socket.connect(classificationPort, classificationHost, () => {
          console.log(`Connected to classification server for ${screenshotPath}`);
          // Just send the path, but don't end the connection - wait for response
          socket.write(`${screenshotPath}\n`);
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
      // Ensure socket is properly closed if still open
      if (socket && !socket.destroyed) {
        socket.destroy();
      }
      span.end();
    }
  });
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

async function detectNavigationOrNewTab(page) {
  let timeoutId = null;
  let targetListener = null;
  let navigationPromise = null;
  
  const waitForNavigationResult = tracer.startActiveSpan('detectNavigationOrNewTab', async (span) => {
    try {
      const timeout = 5000;
      const browser = page.browser();
      
      // Create a cleanup function to remove all listeners
      const cleanup = () => {
        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }
        if (targetListener && browser) {
          browser.off('targetcreated', targetListener);
          targetListener = null;
        }
      };
      
      return await new Promise((mainResolve) => {
        // First promise: navigation on the same page
        navigationPromise = page.waitForNavigation({ timeout })
          .then((result) => {
            console.log('Navigation detected.');
            span.setAttribute('navigation_type', 'same_page');
            cleanup();
            mainResolve(page);
            return page;
          })
          .catch(() => null);  // Just return null on timeout
        
        // Second promise: new tab detection
        targetListener = async (target) => {
          if (target.opener() === page.target()) {
            const newPage = await target.page();
            await newPage.bringToFront();
            console.log('New tab detected.');
            span.setAttribute('navigation_type', 'new_tab');
            cleanup();
            mainResolve(newPage);
          }
        };
        
        browser.on('targetcreated', targetListener);
        
        // Set the timeout to handle the case where neither navigation nor new tab occurs
        timeoutId = setTimeout(() => {
          console.log('Navigation/tab timeout reached.');
          span.setAttribute('navigation_type', 'none');
          cleanup();
          mainResolve(null);
        }, timeout);
      });
    } catch (error) {
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
  
  return waitForNavigationResult;
}

// Function to perform the flow for a given combination of select options.
// NOTE: We now pass an additional parameter "mapping" to apply the select values to duplicate selects.
async function performFlow(browser, url, parentDir, client, selectCombination, mapping, flowIndex, clickLimit, classificationPromisesArray) {
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
      await continueFlow(page, url, client, parentDir, flowIndex, 1, 0, clickLimit, selectCombination, actions, classificationPromisesArray);
      
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

async function continueFlow(page, url, client, parentDir, flowIndex, screenshotIndex, clickCount, clickLimit, selectCombination, actions, classificationPromisesArray) {
  return tracer.startActiveSpan(`continueFlow_${flowIndex}`, async (span) => {
    span.setAttribute('flow_index', flowIndex);
    span.setAttribute('initial_click_count', clickCount);
    span.setAttribute('click_limit', clickLimit);
    
    try {
      const flowDirName = generateFlowDirectoryName(flowIndex);
      const flowDir = path.join(parentDir, flowDirName);

      await fillInputFields(page);

      // Function to take screenshots
      const takeScreenshot = async () => {
        return tracer.startActiveSpan('takeScreenshot', async (screenshotSpan) => {
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
        });
      };
      
      console.log('Filled input fields, now taking screenshot');
      let { screenshotPath, currentUrl } = await takeScreenshot();
      console.log('Sending screenshot for classification');
      
      classificationPromisesArray.push(
        classifyScreenshot(screenshotPath)
        .then(() => console.log(`Classification sent for ${screenshotPath}`))
        .catch(err => console.error(`Error sending screenshot ${screenshotPath}: ${err}`))
      )

      // Track previously clicked positions to avoid infinite loops
      const clickedPositions = new Set();
      let previousElementHTML = null;
      let shouldBreakLoop = false; // Flag to track if we should break the outer loop

      // Main loop to interact with elements based on server response
      while (clickCount < clickLimit && !shouldBreakLoop) {
        await tracer.startActiveSpan(`click_interaction_${clickCount}`, async (clickSpan) => {
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
              shouldBreakLoop = true; // Signal to break the outer loop
              return; // Exit the span
            } else if (clickPosition === 'No popups found') {
              console.log('No popups found');
              clickSpan.setAttribute('result', 'no_popups');
              shouldBreakLoop = false; // Signal to break the outer loop
              return; // Exit the span
            } else if (!match) {
              console.error(`Invalid data received from socket: ${clickPosition}`);
              clickSpan.setAttribute('result', 'invalid_data');
              clickSpan.recordException(new Error(`Invalid click position: ${clickPosition}`));
              shouldBreakLoop = true; // Signal to break the outer loop
              return; // Exit the span
            }

            const [x, y] = match.slice(1).map(Number);
            const positionKey = `${x},${y}`;
            
            // Check if we've already clicked this position
            if (clickedPositions.has(positionKey)) {
              console.log(`Already clicked at position (${x}, ${y}). Skipping to avoid infinite loop.`);
              clickSpan.setAttribute('result', 'repeated_click_position');
              shouldBreakLoop = true; // Signal to break the outer loop
              return; // Exit the span
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
              shouldBreakLoop = true; // Signal to break the outer loop
              return; // Exit the span
            }

            // Log element found at position for debugging
            console.log(`Element at position (${x}, ${y}): ${currentElementHTML.slice(0, 100)}...`);
            
            // If it's the same element as previous, we should break
            if (currentElementHTML === previousElementHTML) {
              console.log('Same element as previous click detected. Stopping flow to avoid loop.');
              clickSpan.setAttribute('result', 'repeated_element');
              clickSpan.setAttribute('same_as_previous', true);
              
              // Add a final action with this click position
              actions.push({
                step: actions.length,
                clickPosition: { x, y },
                elementHTML: truncateString(currentElementHTML),
                screenshot: screenshotPath,
                url: currentUrl,
                note: "Flow stopped: same element as previous click"
              });
              
              shouldBreakLoop = true; // Signal to break the outer loop
              return; // Exit the span
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
            classificationPromisesArray.push(
              classifyScreenshot(screenshotPath)
              .then(() => console.log(`Classification sent for ${screenshotPath}`))
              .catch(err => console.error(`Error sending screenshot ${screenshotPath}: ${err}`))
            )
              
            clickSpan.setAttribute('result', 'success');
          } catch (error) {
            clickSpan.recordException(error);
            shouldBreakLoop = true; // Signal to break the outer loop
            throw error;
          } finally {
            clickSpan.end();
          }
        }).catch(error => {
          // If we get an error in the active span
          console.error(`Error during click interaction: ${error.message}`);
          shouldBreakLoop = true; // Make sure we break the loop on errors
        });

        // If any of the conditions that would cause an exit were met in the span,
        // we should break the loop here
        if (shouldBreakLoop) {
          break;
        }
      }

      // After the loop, if we need a final entry, add one
      if ((shouldBreakLoop || clickCount >= clickLimit) && 
          (actions.length === 0 || actions[actions.length - 1].clickPosition !== null)) {
        actions.push({
          step: actions.length,
          clickPosition: null,
          elementHTML: null,
          screenshot: screenshotPath,
          url: currentUrl,
          note: shouldBreakLoop ? "Flow terminated early" : "Click limit reached"
        });
      }
      
      // Write actions to JSON file for this specific flow
      await tracer.startActiveSpan('write_actions_json', async (writeSpan) => {
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
      });
      
      span.setAttribute('total_clicks', clickCount);
      span.setAttribute('actions_recorded', actions.length);
      span.setAttribute('early_termination', shouldBreakLoop);
      
    } catch (error) {
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}
async function connectSocketWithRetry(host, port) {
  return tracer.startActiveSpan('socket_connection', async (span) => {
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
  });
}
async function runCrawler(url) {
  return tracer.startActiveSpan('runCrawler', async (span) => {
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
      browser = await tracer.startActiveSpan('browser_launch', async (browserSpan) => {
        try {
          const browser = await puppeteer.launch({
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
          return browser;
        } catch (error) {
          browserSpan.recordException(error);
          throw error;
        } finally {
          browserSpan.end();
        }
      });

      const CLICK_LIMIT = 5;
      span.setAttribute('click_limit', CLICK_LIMIT);

      // Clean up the contents of the parent directory without deleting the directory itself
      const parentDir = path.join(__dirname, '/screenshot_flows', generateParentDirectoryName(url));
      span.setAttribute('parent_dir', parentDir);
      console.log(`Parent directory path: ${parentDir}`);

      await tracer.startActiveSpan('cleanup_directory_contents', async (cleanupSpan) => {
        try {
          // Create the directory if it doesn't exist
          if (!fs.existsSync(parentDir)) {
            fs.mkdirSync(parentDir, { recursive: true });
            console.log(`Created parent directory: ${parentDir}`);
            return; // New directory, nothing to clean up
          }
          
          console.log(`Cleaning up contents of existing directory: ${parentDir}`);
          cleanupSpan.setAttribute('directory', parentDir);
          
          // List all contents (for debugging and cleanup)
          const dirContents = fs.readdirSync(parentDir);
          console.log(`Directory contents to clean: ${dirContents.length} items`);
          cleanupSpan.setAttribute('item_count', dirContents.length);
          
          // Function to recursively delete directory contents without removing the root directory
          const cleanDirectoryContents = function(dirPath, isRoot = true) {
            if (fs.existsSync(dirPath)) {
              // Process each file/directory inside
              fs.readdirSync(dirPath).forEach((file) => {
                const curPath = path.join(dirPath, file);
                
                try {
                  if (fs.lstatSync(curPath).isDirectory()) {
                    // For subdirectories: delete everything inside, then the directory itself
                    cleanDirectoryContents(curPath, false);
                    // Only delete non-root directories
                    if (!isRoot) {
                      fs.rmdirSync(curPath);
                      console.log(`Deleted subdirectory: ${curPath}`);
                    }
                  } else {
                    // Delete file
                    fs.unlinkSync(curPath);
                    console.log(`Deleted file: ${curPath}`);
                  }
                } catch (e) {
                  console.error(`Failed to process ${curPath}: ${e.message}`);
                  cleanupSpan.recordException(e);
                }
              });
            }
          };
          
          // Clean directory contents but keep the parent directory
          cleanDirectoryContents(parentDir);
          console.log(`Completed cleaning directory contents`);
          
          // Verify the contents are gone but directory remains
          const remainingItems = fs.existsSync(parentDir) ? fs.readdirSync(parentDir).length : 0;
          cleanupSpan.setAttribute('remaining_items', remainingItems);
          console.log(`Directory cleanup complete. Remaining items: ${remainingItems}`);
          
        } catch (err) {
          console.error(`Unexpected error during directory cleanup: ${err.message}`);
          cleanupSpan.recordException(err);
        } finally {
          cleanupSpan.end();
        }
      });

      // Open a page to get the select options
      let selectOptions = [];
      await tracer.startActiveSpan('get_initial_select_options', async (selectSpan) => {
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
      });
      classificationPromises = []

      if (selectOptions.length === 0) {
        console.log("No select options found. Running flow without select options.");
        span.setAttribute('has_select_options', false);
        // Passing null as selectCombination and an empty array for mapping.
        await performFlow(browser, url, parentDir, client, null, [], 0, CLICK_LIMIT, classificationPromises);
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
          await performFlow(browser, url, parentDir, client, selectCombination, mapping, i, CLICK_LIMIT, classificationPromises);
        }
      }
    } catch (error) {
      console.error('Error:', error);
      span.recordException(error);
    } finally {
      if (browser) {
        await Promise.all(classificationPromises)
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
  });
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
  return tracer.startActiveSpan('crawler_execution', async (mainSpan) => {
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
  });
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