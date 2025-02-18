import pika
import logging
import json
import time
import threading
import multiprocessing
import ssl
import requests
from modules.analyzers import ANALYZER


logger = logging.getLogger(__name__)


class RabbitHelper:

    # def publish_login_candidates(self, candidates):
    #     """
    #     Publish the preprocessed login candidates to a new queue named 'login_candidates'.
    #     'candidates' should be a Python list/dict that can be serialized to JSON.
    #     """
    #     new_queue = "login_candidates"

    #     # Define queue arguments:
    #     # - x-message-ttl: 24 hours in milliseconds (86400000)
    #     # - x-max-length-bytes: 536 MB (536870912)
    #     arguments = {
    #         "x-message-ttl":86400000,           # Message time-to-live in ms
    #         "x-max-length-bytes": 536870912      # Maximum total size of the queue in bytes
    #     }

    #     # Declare the new queue with the given arguments (this is idempotent)
    #     self.channel.queue_declare(queue=new_queue, durable=True, arguments=arguments)
        
    #     # Serialize the candidates to a JSON string and encode it to bytes
    #     message_body = json.dumps(candidates).encode('utf-8')
        
    #     # Publish the message to the new queue
    #     self.channel.basic_publish(
    #         exchange="",
    #         routing_key=new_queue,
    #         body=message_body,
    #         properties=pika.BasicProperties(
    #             delivery_mode=2  # Make message persistent
    #         )
    #     )
    #     print(f"Published login candidates to queue '{new_queue}'")
    #     logger.info(f"Published login candidates to queue '{new_queue}'")

    def send_candidates_to_api(candidates):
        """
        Send the preprocessed login candidates to a remote API endpoint.
        'candidates' should be a Python list/dict that can be serialized to JSON.
        """
        # Construct the target URL for the API endpoint. Change the path as needed.
        api_url = "http://host.docker.internal:4000/api/login_candidates"
        
        # Serialize candidates to JSON.
        payload = json.dumps(candidates)
        
        try:
            # Send a POST request with the JSON payload.
            response = requests.post(
                api_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
            )
        except Exception as e:
            logger.error("Error sending candidates to API: %s", e, exc_info=True)
            return False

        if response.status_code != 200:
            logger.warning("Failed to send candidates to API. Status code: %s", response.status_code)
            return False

        logger.info("Successfully sent login candidates to API at %s", api_url)
        return True




    def preprocess_candidates(input_json):
        """
        Given an input JSON object containing landscape_analysis_result with login_page_candidates,
        this function deduplicates candidates by URL. If there are duplicates and one candidate has 
        login_page_strategy 'CRAWLING', that candidate is kept.
        
        The output is a list of dicts with keys: id, url, actions, and scan_domain.
        """
        # Extract the list of candidates from the input JSON.
        candidates = input_json.get("landscape_analysis_result", {}).get("login_page_candidates", [])
        
        # Extract the scan domain from scan_config (if present)
        scan_domain = input_json.get("scan_config", {}).get("domain", "")
        
        # Group candidates by their URL.
        grouped = {}
        for candidate in candidates:
            url = candidate.get("login_page_candidate", "").strip()
            if not url:
                continue  # Skip if no URL is provided.
            grouped.setdefault(url, []).append(candidate)
        
        # Process each group and choose one candidate per URL.
        output = []
        id_counter = 1
        for url, group in grouped.items():
            # Try to find a candidate with login_page_strategy == 'CRAWLING' (case-insensitive)
            chosen = None
            for candidate in group:
                if candidate.get("login_page_strategy", "").upper() == "CRAWLING":
                    chosen = candidate
                    break
            # If no candidate is marked as CRAWLING, select the first candidate in the group.
            if not chosen:
                chosen = group[0]
            
            # Extract the 'login_page_actions' if it exists. Otherwise, set to None.
            actions = chosen.get("login_page_actions", None)
            
            # Build the output dictionary including the scan domain.
            output.append({
                "id": id_counter,
                "url": url,
                "actions": actions,  # This will be None if not present.
                "scan_domain": scan_domain
            })
            id_counter += 1

        return output




    def __init__(
        self, admin_user: str, admin_password: str,
        rabbit_host: str, rabbit_port: int, rabbit_tls: str, rabbit_queue: str, brain_url: str
    ):
        logger.info(f"Connecting to rabbitmq: {admin_user}:{admin_password}@{rabbit_host}:{rabbit_port} (tls={rabbit_tls})")
        logger.info(f"Connecting to queue: {rabbit_queue}")
        logger.info(f"Connecting to brain: {admin_user}:{admin_password}@{brain_url}")

        # brain credentials
        self.brain_url = brain_url
        self.brain_user = admin_user
        self.brain_password = admin_password
        self.vv8_url = ''

        # rabbit credentials
        self.credentials = pika.PlainCredentials(admin_user, admin_password)
        if rabbit_tls == "1": # tls
            ctx = ssl.SSLContext()
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.check_hostname = True
            ctx.load_default_certs()
            self.parameters = pika.ConnectionParameters(
                host=rabbit_host, port=rabbit_port, credentials=self.credentials,
                ssl_options=pika.SSLOptions(ctx)
            )
        else: # no tls
            self.parameters = pika.ConnectionParameters(
                host=rabbit_host, port=rabbit_port, credentials=self.credentials
            )

        # rabbit connection
        self.connection = pika.BlockingConnection(self.parameters)
        self.channel = self.connection.channel()
        self.channel.basic_qos(prefetch_count=1) # only fetch one message at a time

        # rabbit queue
        self.queue = rabbit_queue
        self.analysis = rabbit_queue.replace("_treq", "")
        self.channel.queue_declare(queue=self.queue, durable=True)
        self.channel.basic_consume(queue=self.queue, on_message_callback=self.on_message_callback)


    def on_message_callback(self, channel, method, properties, body):
        logger.info(f"Received message on queue: {self.queue}")
        t = threading.Thread(target=self.analyzer_executor, args=(channel, method, properties, body))
        t.daemon = True
        t.start()


    def analyzer_executor(self, channel, method, properties, body):
        logger.info(f"Executing message on queue: {self.queue}")

        tres = json.loads(body)

        tres["task_config"]["task_state"] = "REQUEST_RECEIVED"
        tres["task_config"]["task_timestamp_request_received"] = time.time()

        pool = multiprocessing.Pool(processes=1)
        workers = pool.apply_async(self.analyzer_process, args=(self.analysis, tres["domain"], tres[f"{self.analysis}_config"]))

        try:
            tres[f"{self.analysis}_result"] = workers.get(timeout=60*60*3) # 3 hours
            logger.info(f"Process finished executing message on queue: {self.queue}")
        except multiprocessing.TimeoutError:
            logger.error(f"Process timeout executing message on queue: {self.queue}")
            tres[f"{self.analysis}_result"] = {"exception": "Process timeout"}
            pool.terminate()
        finally:
            pool.close()
            pool.join()

        tres["task_config"]["task_state"] = "RESPONSE_SENT"
        tres["task_config"]["task_timestamp_response_sent"] = time.time()

        self.connection.add_callback_threadsafe(lambda: self.reply_data_and_ack_msg(channel, method, properties, tres))


    @staticmethod
    def analyzer_process(analysis: str, domain: str, config: dict) -> dict:
        try:
            return ANALYZER[analysis](domain, config).start()
        except Exception as e:
            logger.error(f"Exception while executing analyzer process: {analysis}")
            logger.debug(e)
            return {"exception": f"{e}"}


    def reply_data_and_ack_msg(self, channel, method, properties, data):
        logger.info(f"Reply data and acknowledge message received on queue: {self.queue}")
        print(f'Sending data to reply_data: {data}')
        logger.info(f'Sending data to reply_data: {data}')
        # Preprocess candidates using the static method
        candidates = RabbitHelper.preprocess_candidates(data)
        print('Candidates:', candidates)
        logger.info(f'Candidates:{candidates}')
        # Publish them to the 'login_candidates' api
        RabbitHelper.send_candidates_to_api(candidates)
        if properties.reply_to:
            while True:
                success = self.reply_data(properties.reply_to, data)
                if success: break
                else: time.sleep(60)
        logger.info(f"Acknowledge message received on queue: {self.queue}")
        channel.basic_ack(delivery_tag=method.delivery_tag)


    def reply_data(self, reply_to: str, data: dict) -> bool:
        logger.info(f"Reply data from message received on queue {self.queue} to: {reply_to}")
        try:
            r = requests.put(f"{self.brain_url}{reply_to}", json=data, auth=(self.brain_user, self.brain_password))
        except Exception as e:
            logger.warning(f"Exception while replying data to: {reply_to}")
            logger.debug(e)
            return False
        if r.status_code != 200:
            logger.warning(f"Invalid status code ({r.status_code}) while replying data to: {reply_to}")
            return False
        print(f'Sending data back to brain: {data}')
        logger.info(f'Sending data back to brain: {data}')
        logger.info(f"Successfully replied data to: {reply_to}")
        return True
