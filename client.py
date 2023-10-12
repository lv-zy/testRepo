import socket
import struct
import threading
import re

SERVER_IP = "101.42.155.69"
SERVER_PORT = 11451
BUFFER_SIZE = 1024

class FTPCommand:
    def __init__(self):
        self.command = ""
        self.argument = ""

class IPAddress:
    def __init__(self):
        self.ip = ""
        self.port = 0

class ClientSession:
    def __init__(self):
        self.login_status = 0
        self.email = ""
        self.path = ""
        self.ip = "127.0.0.1"
        self.port = 0
        self.transfer_mode = 0
        self.in_used = 0
        self.sockfd = None
        self.state = "normal"  # Add state to track the FTP client's current state

def parseIPAddress(input_str):
    try:
        h1, h2, h3, h4, p1, p2 = map(int, input_str.split(','))
        ip_address = IPAddress()
        ip_address.ip = f"{h1}.{h2}.{h3}.{h4}"
        ip_address.port = p1 * 256 + p2
        return ip_address
    except:
        return None

def parse_ftp_command(input_str:str):
    cmd = FTPCommand()

    parts = input_str.split(' ', 1)
    cmd.command = parts[0].upper()
    if len(parts) > 1:
        cmd.argument = parts[1]

    return cmd

def handle_pasv_retr(se):
    print("[debug] pasv retr")

    with open("received_file.txt", "wb") as file:
        while True:
            data = se.sockfd.recv(BUFFER_SIZE)
            if not data:
                break
            file.write(data)
    se.state = "normal"


def original_handle_retr(recv_port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', recv_port))
    server_socket.listen(1)

    server_socket.settimeout(2)  # 设置超时为10秒

    try:
        client_socket, _ = server_socket.accept()

        with open("received_file.txt", "wb") as file:
            while True:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break
                file.write(data)

        client_socket.close()
        # print("File received")
    except socket.timeout:
        print("Socket operation timed out.")
    finally:
        server_socket.close()

def handle_pasv_text_retr(se):
    print("[debug] handle pasv text retr")
    
    received_text = []
    while True:
        data = se.sockfd.recv(BUFFER_SIZE)
        if not data:
            break
        received_text.append(data.decode())
    
    complete_text = "".join(received_text)
    print(complete_text)
    se.state = "normal"

def handle_port_list(se, recv_port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', recv_port))
    server_socket.listen(1)

    server_socket.settimeout(2)  # 设置超时为10秒

    try:
        client_socket, _ = server_socket.accept()

        received_text = []
        while True:
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                break
            received_text.append(data.decode())
        
        complete_text = "".join(received_text)
        print(complete_text)
        se.state = "normal"

        client_socket.close()
    except socket.timeout:
        print("Socket operation timed out.")
    finally:
        server_socket.close()


def handle_command(cmd, se):
    if cmd.command == "RETR":
        if se.state == "pasv":
            # handle_pasv_retr(se)
            t = threading.Thread(target=handle_pasv_retr, args=(se,))
            t.start()
        else:
            t = threading.Thread(target=original_handle_retr, args=(se.port,))
            t.start()
    elif cmd.command == "PORT":
        ip_address = parseIPAddress(cmd.argument)
        if ip_address:
            se.ip = ip_address.ip
            se.port = ip_address.port
    elif cmd.command == "STOR":
        if se.state == "pasv":
            t = threading.Thread(target=handle_pasv_stor, args=(se, cmd.argument))
            t.start()
        else:
            t = threading.Thread(target=original_handle_stor, args=(se.port, cmd.argument))
            t.start()
    elif cmd.command == "LIST":
        if se.state == "pasv":
            t = threading.Thread(target=handle_pasv_text_retr, args=(se,))
            t.start()
        else:
            t = threading.Thread(target=handle_port_list, args=(se, se.port,))
            t.start()
            
    elif cmd.command == "PASV":
        
        pass

def send_file_to_socket(file_path, socket):
    try:
        with open(file_path, "rb") as file:
            while True:
                print("[debug] reading..")
                data = file.read(BUFFER_SIZE)
                print("[debug] readed")
                if not data:
                    break
                print("[debug] sending file")
                socket.sendall(data)
                print("[debug] sent")
        return True
    except:
        print("[fatal] open failed")
        return False

def handle_pasv_stor(se, filename):
    print("[debug] pasv stor")
    send_file_to_socket(filename, se.sockfd)
    se.sockfd.close()
    se.state = "normal"

def original_handle_stor(send_port, filename):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', send_port))
    server_socket.listen(1)

    server_socket.settimeout(2)  # 设置超时为10秒

    try:
        client_socket, _ = server_socket.accept()
        send_file_to_socket(filename, client_socket)
        client_socket.close()
        # print("File sent")
    except socket.timeout:
        print("Socket operation timed out.")
    finally:
        server_socket.close()



def process_reply(msg : str, session : ClientSession):
    # 正则表达式用于匹配 "Entering Passive Mode (127,0,0,1,%d,%d)" 并提取两个数字
    pattern = r"Entering Passive Mode \(127,0,0,1,(\d+),(\d+)\)"
    match = re.search(pattern, msg)
    
    if match:
        # 获取匹配的两个数字
        p1 = int(match.group(1))
        p2 = int(match.group(2))
        
        # 设置session的IP和端口
        session.ip = SERVER_IP
        session.port = p1 * 256 + p2
        session.state = 'pasv'
        print("[info] client entering pasv mode")
        try:
            session.sockfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            session.sockfd.connect((session.ip, session.port))
            print("[info] data connected")
            
        except Exception as e:
            print(f"Error: {e}")


def main():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((SERVER_IP, SERVER_PORT))
    
    welcome_msg = client_socket.recv(BUFFER_SIZE).decode()
    print(welcome_msg)
    
    current_session = ClientSession()

    while True:
        input_cmd = input(" > ")

        if input_cmd == "exit":
            break
        if input_cmd == "pydbg":
            print(current_session.port)
            continue
            

        cmd = parse_ftp_command(input_cmd)
        handle_command(cmd, current_session)

        client_socket.sendall((input_cmd + '\r\n').encode())
        response = client_socket.recv(BUFFER_SIZE).decode().strip()
        process_reply(response, current_session)
        print(f"--->{response}")

    client_socket.close()

if __name__ == "__main__":
    main()
