// otel-setup.js
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { resourceFromAttributes, defaultResource } = require('@opentelemetry/resources');
const {ATTR_SERVICE_NAME} = require('@opentelemetry/semantic-conventions');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-grpc');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc');
const { PeriodicExportingMetricReader, MeterProvider } = require('@opentelemetry/sdk-metrics');
const {metrics} = require('@opentelemetry/api')
const { diag, DiagConsoleLogger, DiagLogLevel } = require('@opentelemetry/api');
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);


// Configure OTLP exporters
const traceExporter = new OTLPTraceExporter({
  host: '172.17.0.1',
  port: '4317', // Collector's OTLP endpoint for traces
});
const metricExporter = new OTLPMetricExporter({
  host: '172.17.0.1',
  port: '4317', // Collector's OTLP endpoint for metrics
});

const resource = defaultResource().merge(
  resourceFromAttributes({
    [ATTR_SERVICE_NAME]: 'sso-crawler-service',
  }),
)


// Set up the OpenTelemetry SDK
const sdk = new NodeSDK({
  resource: resource,
  traceExporter: traceExporter,
  metricReader: new PeriodicExportingMetricReader({
    exporter: metricExporter,
    exportIntervalMillis: 15000, // Export metrics every 15 seconds
  }),
});

// Start the SDK
sdk.start()


module.exports = { sdk };

/*
export OTEL_EXPORTER_OTLP_ENDPOINT="http://172.17.0.1:4317"

*/