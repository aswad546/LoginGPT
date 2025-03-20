// OpenTelemetry configuration for crawler.js
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { Resource } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');
const { PrometheusExporter } = require('@opentelemetry/exporter-prometheus');
const { JaegerExporter } = require('@opentelemetry/exporter-jaeger');
const { SimpleSpanProcessor } = require('@opentelemetry/sdk-trace-base');
const { metrics, trace } = require('@opentelemetry/api');
const { MeterProvider } = require('@opentelemetry/sdk-metrics');

// Configuration from environment variables
const JAEGER_ENDPOINT = process.env.JAEGER_ENDPOINT || 'http://localhost:14268/api/traces';
const PROMETHEUS_PORT = parseInt(process.env.PROMETHEUS_PORT || '9464');
const SERVICE_NAME = process.env.SERVICE_NAME || 'login-page-detection';

// Set up Prometheus exporter
const prometheusExporter = new PrometheusExporter({
  port: PROMETHEUS_PORT,
  startServer: true,
});

// Configure Jaeger exporter
const jaegerExporter = new JaegerExporter({
  endpoint: JAEGER_ENDPOINT,
});

// Create and configure the meter provider with the Prometheus exporter
const meterProvider = new MeterProvider({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: SERVICE_NAME,
    [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
  }),
});
meterProvider.addMetricReader(prometheusExporter);
metrics.setGlobalMeterProvider(meterProvider);

// Create the SDK with tracing enabled
const sdk = new NodeSDK({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: SERVICE_NAME,
    [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
  }),
  traceExporter: jaegerExporter,
  spanProcessor: new SimpleSpanProcessor(jaegerExporter),
  instrumentations: [getNodeAutoInstrumentations()],
});

// Start the SDK
sdk.start();

// Create tracer and meter for manual instrumentation
const meter = metrics.getMeter(SERVICE_NAME);
const tracer = trace.getTracer(SERVICE_NAME);

// Define key metrics
const pageLoadDuration = meter.createHistogram('page_load_duration_seconds', {
  description: 'Duration of page loads in seconds',
  unit: 's'
});

const classificationDuration = meter.createHistogram('classification_duration_seconds', {
  description: 'Duration of screenshot classification in seconds',
  unit: 's'
});

const clickPositionDuration = meter.createHistogram('click_position_duration_seconds', {
  description: 'Duration of click position inference in seconds',
  unit: 's'
});

const screenshotsTotal = meter.createCounter('screenshots_total', {
  description: 'Total number of screenshots taken'
});

const flowsCompleted = meter.createCounter('flows_completed_total', {
  description: 'Total number of completed crawler flows'
});

// Export the objects for use in crawler.js
module.exports = {
  meter,
  tracer,
  metrics: {
    pageLoadDuration,
    classificationDuration,
    clickPositionDuration,
    screenshotsTotal,
    flowsCompleted
  },
  shutdown: () => sdk.shutdown()
};