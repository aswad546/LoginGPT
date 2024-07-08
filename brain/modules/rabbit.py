import pika
import logging
import json
from pika.exceptions import StreamLostError


logger = logging.getLogger(__name__)


class Rabbit:


    def __init__(self, host, port, user, passwd):
        logger.info(f"Connecting to rabbitmq: {host}:{port} ({user}:{passwd})")
        self.credentials = pika.PlainCredentials(user, passwd)
        self.parameters = pika.ConnectionParameters(host=host, port=port, credentials=self.credentials)
        self.connection = pika.BlockingConnection(self.parameters)
        self.channel = self.connection.channel()
        self.channel.basic_qos(prefetch_count=1) # only fetch one task at a time
        self.declared_queues = []


    def queue_declare(self, *args, **kwargs):
        """ wrapper to avoid declaring same queue multiple times (slow) """
        if kwargs["queue"] not in self.declared_queues:
            self.channel.queue_declare(*args, **kwargs)
            self.declared_queues.append(kwargs["queue"])


    #### producer of task requests ####


    def send_treq(self, queue, reply_to, correlation_id, treq, retry=False):
        logger.info(f"Sending task request to {queue} (reply_to: {reply_to}, correlation_id: {correlation_id})")
        properties = pika.BasicProperties()
        properties.content_type = "application/json"
        properties.delivery_mode = pika.spec.PERSISTENT_DELIVERY_MODE
        properties.reply_to = reply_to
        properties.correlation_id = correlation_id
        try:
            self.queue_declare(queue=queue, durable=True)
            self.channel.basic_publish(
                exchange="",
                routing_key=queue,
                body=json.dumps(treq),
                properties=properties
            )
            logger.info(f"Successfully sent task request to {queue}")
            return {"success": True, "error": None, "data": None}
        except StreamLostError as e:
            logger.error(f"Failed to send task request to {queue}: {e}")
            if retry: return {"success": False, "error": str(e), "data": None} # only try reconnect once
            logger.error(f"Reconnecting to rabbitmq: {self.parameters.host}:{self.parameters.port}")
            self.connection = pika.BlockingConnection(self.parameters)
            self.channel = self.connection.channel()
            self.channel.basic_qos(prefetch_count=1)
            return self.send_treq(queue, reply_to, correlation_id, treq, retry=True)
        except Exception as e:
            logger.error(f"Failed to send task request to {queue}: {e}")
            return {"success": False, "error": str(e), "data": None}
