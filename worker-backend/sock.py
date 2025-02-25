#!/usr/bin/env python3
import socket

def main():
    # Use the same host and port as your server (adjust if needed)
    HOST = '127.0.0.1'  # or your server's IP address
    PORT = 5000

    # The image path you want to test (adjust to match an existing file on your system)
    image_path = "/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/screenshot_flows/www_illimitybank_com/flow_0/page_1.png"
    
    # Create a socket connection to the server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print(f"Connected to server at {HOST}:{PORT}")
        
        # Send the image path to the server
        s.sendall(image_path.encode('utf-8'))
        print(f"Sent image path: {image_path}")
        
        # Optionally, wait for a response from the server (up to 1024 bytes)
        response = s.recv(1024)
        print("Received response:", response.decode('utf-8'))

        image_path = "/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/screenshot_flows/www_illimitybank_com/flow_0/page_3.png"
        s.sendall(image_path.encode('utf-8'))
        print(f"Sent image path: {image_path}")
        
        # Optionally, wait for a response from the server (up to 1024 bytes)
        response = s.recv(1024)
        print("Received response:", response.decode('utf-8'))

if __name__ == "__main__":
    main()
