import socket

HOST = "127.0.0.1"  # Adjust if needed.
PORT = 5060         # Must match the server port.

# The image path you want to test.
image_path = "/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/screenshot_flows/www_hancockwhitney_com__/flow_1/page_1.png"

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(image_path.encode('utf-8'))
    data = s.recv(1024)
    print("Received response:", data.decode('utf-8'))
