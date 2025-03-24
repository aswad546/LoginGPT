// mock-example.js
const { sdk, meterProvider } = require('./otel-setup');
const { trace, metrics, context } = require('@opentelemetry/api');
const axios = require('axios');

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Get a tracer and meter
const tracer = trace.getTracer('web-crawler-tracer');
const meter = metrics.getMeter('web-crawler-meter');
console.log(tracer);
console.log(meter);
const counter = meter.createCounter('sleepForTime.counter');

async function sleepForTime(timeToSleep) {
  return tracer.startActiveSpan('span-1', async (span) => {
    counter.add(1);
    await sleep(timeToSleep);
    span.setAttribute('sleep.duration_ms', timeToSleep);
    span.end();
    return timeToSleep;
  });
}

sleepForTime(3000)
  .then(() => {
    console.log('Span completed and data should be sent to the collector.');
    // Optionally, shutdown the SDK to flush data before exit:
    return sdk.shutdown();
  })
  .catch(err => {
    console.error('Error during span execution:', err);
  });
