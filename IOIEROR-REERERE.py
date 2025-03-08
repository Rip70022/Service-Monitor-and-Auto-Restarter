import os
import socket
import subprocess
import time
import threading
import signal
import sys
import datetime
from termcolor import colored

SERVICES_CONFIG = {
    "ssh": {
        "service_name": "sshd",
        "port": 22,
        "restart_command": "systemctl restart sshd",
        "status_command": "systemctl status sshd",
    },
    "nginx": {
        "service_name": "nginx",
        "port": 80,
        "restart_command": "systemctl restart nginx",
        "status_command": "systemctl status nginx",
    },
    "apache": {
        "service_name": "apache2",
        "port": 80,
        "restart_command": "systemctl restart apache2",
        "status_command": "systemctl status apache2",
    },
    "mysql": {
        "service_name": "mysql",
        "port": 3306,
        "restart_command": "systemctl restart mysql",
        "status_command": "systemctl status mysql",
    },
    "postgresql": {
        "service_name": "postgresql",
        "port": 5432,
        "restart_command": "systemctl restart postgresql",
        "status_command": "systemctl status postgresql",
    },
    "mongodb": {
        "service_name": "mongod",
        "port": 27017,
        "restart_command": "systemctl restart mongod",
        "status_command": "systemctl status mongod",
    },
    "redis": {
        "service_name": "redis-server",
        "port": 6379,
        "restart_command": "systemctl restart redis-server",
        "status_command": "systemctl status redis-server",
    },
    "docker": {
        "service_name": "docker",
        "port": None,
        "restart_command": "systemctl restart docker",
        "status_command": "systemctl status docker",
    }
}

monitored_services = {}
log_file = "service_monitor.log"
stop_event = threading.Event()

def print_ascii_art():
    ascii_art = """
    ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
    █▄ ▄█ ▄▄▄ █▄ ▄█ ▄▄█ ▄▄▀█ ▄▄▄ █ ▄▄▀███ ▄▄▀█ ▄▄█ ▄▄█ ▄▄▀█ ▄▄▄█ ▄▄▀█ ▄▄▄
    ██ ██ ███ ██ ██ ▄▄█ ▀▀ █ ███ █ ▀▀▄███ ▀▀▄█ ▄▄█ ▄▄█ ▀▀▄█ ▄▄▄█ ▀▀▄█ ▄▄▄
    █▀ ▀█ ▀▀▀ █▀ ▀█▄▄▄█ ██ █ ▀▀▀ █▄█▄▄███▄█▄▄█▄▄▄█▄▄▄█▄█▄▄█▄▄▄▄█▄█▄▄█▄▄▄▄
    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
    """
    print(colored(ascii_art, 'cyan'))
    print(colored("Created by: https://www.github.com/Rip70022", 'yellow'))
    print(colored("Service Monitor & Auto-Restarter v1.0", 'green'))
    print(colored("-" * 70, 'white'))

def clear_screen():
    os.system('clear')

def log_message(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} [{level}] {message}"
    
    with open(log_file, "a") as f:
        f.write(log_entry + "\n")
    
    if level == "ERROR":
        print(colored(log_entry, 'red'))
    elif level == "WARNING":
        print(colored(log_entry, 'yellow'))
    elif level == "SUCCESS":
        print(colored(log_entry, 'green'))
    else:
        print(colored(log_entry, 'white'))

def execute_command(command):
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def is_port_open(host, port):
    if port is None:
        return None
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

def check_service_status(service_name):
    if service_name not in SERVICES_CONFIG:
        return False, "Service not configured"
    
    config = SERVICES_CONFIG[service_name]
    
    returncode, stdout, stderr = execute_command(config["status_command"])
    
    if config["port"] is not None:
        port_status = is_port_open("127.0.0.1", config["port"])
    else:
        port_status = None
    
    if returncode == 0 and (port_status is None or port_status):
        return True, stdout
    else:
        if returncode != 0:
            return False, stderr
        else:
            return False, f"Service is running but port {config['port']} is not open"

def restart_service(service_name):
    if service_name not in SERVICES_CONFIG:
        log_message(f"Cannot restart {service_name}: Service not configured", "ERROR")
        return False
    
    config = SERVICES_CONFIG[service_name]
    
    log_message(f"Attempting to restart {service_name}...", "WARNING")
    returncode, stdout, stderr = execute_command(config["restart_command"])
    
    if returncode == 0:
        log_message(f"Successfully restarted {service_name}", "SUCCESS")
        return True
    else:
        log_message(f"Failed to restart {service_name}: {stderr}", "ERROR")
        return False

def monitor_service(service_name, interval=30):
    service_config = SERVICES_CONFIG.get(service_name)
    if not service_config:
        log_message(f"Cannot monitor {service_name}: Service not configured", "ERROR")
        return
    
    failures = 0
    max_failures = 3
    restart_attempts = 0
    max_restart_attempts = 5
    
    log_message(f"Starting monitoring for {service_name}", "INFO")
    
    while not stop_event.is_set():
        is_running, status_msg = check_service_status(service_name)
        
        if is_running:
            failures = 0
            restart_attempts = 0
            
            monitored_services[service_name]["status"] = "Running"
            monitored_services[service_name]["last_check"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            monitored_services[service_name]["failures"] = failures
            
            time.sleep(interval)
            continue
        
        failures += 1
        monitored_services[service_name]["status"] = "Failed"
        monitored_services[service_name]["last_check"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        monitored_services[service_name]["failures"] = failures
        
        if failures >= max_failures:
            if restart_attempts >= max_restart_attempts:
                log_message(f"Service {service_name} has failed {failures} times and reached maximum restart attempts ({max_restart_attempts})", "ERROR")
                log_message(f"Manual intervention required for {service_name}", "ERROR")
                monitored_services[service_name]["status"] = "Failed - Manual intervention required"
                stop_monitoring_service(service_name)
                break
            
            restart_attempts += 1
            successfully_restarted = restart_service(service_name)
            
            if successfully_restarted:
                failures = 0
                monitored_services[service_name]["status"] = "Restarted"
                monitored_services[service_name]["last_restart"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                monitored_services[service_name]["restart_count"] += 1
            
            time.sleep(10)  # Give the service some time to start up before checking again
        else:
            log_message(f"Service {service_name} appears to be down (failure {failures}/{max_failures})", "WARNING")
            time.sleep(interval / 2)  # Check more frequently during potential failure

def start_monitoring_service(service_name, interval=30):
    if service_name in monitored_services and monitored_services[service_name]["thread"] and monitored_services[service_name]["thread"].is_alive():
        log_message(f"Service {service_name} is already being monitored", "WARNING")
        return False
    
    is_running, status_msg = check_service_status(service_name)
    initial_status = "Running" if is_running else "Not running"
    
    monitored_services[service_name] = {
        "thread": None,
        "status": initial_status,
        "last_check": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_restart": "Never",
        "restart_count": 0,
        "failures": 0,
        "interval": interval
    }
    
    thread = threading.Thread(target=monitor_service, args=(service_name, interval))
    thread.daemon = True
    thread.start()
    
    monitored_services[service_name]["thread"] = thread
    log_message(f"Started monitoring service {service_name} at {interval} second intervals", "SUCCESS")
    return True

def stop_monitoring_service(service_name):
    if service_name not in monitored_services or not monitored_services[service_name]["thread"]:
        log_message(f"Service {service_name} is not currently being monitored", "WARNING")
        return False
    
    if monitored_services[service_name]["thread"].is_alive():
        monitored_services[service_name]["status"] = "Monitoring stopped"
        log_message(f"Stopped monitoring service {service_name}", "INFO")
        
        if service_name in monitored_services:
            del monitored_services[service_name]
        
        return True
    else:
        if service_name in monitored_services:
            del monitored_services[service_name]
        
        log_message(f"Monitoring thread for {service_name} was not active", "WARNING")
        return False

def get_available_services():
    return list(SERVICES_CONFIG.keys())

def signal_handler(sig, frame):
    print(colored("\n\nShutting down service monitor...", 'yellow'))
    stop_event.set()
    sys.exit(0)

def display_dashboard():
    clear_screen()
    print_ascii_art()
    
    print(colored("SERVICES MONITORING DASHBOARD", 'green'))
    print(colored("-" * 70, 'white'))
    
    if not monitored_services:
        print(colored("No services currently being monitored", 'yellow'))
    else:
        print(colored("{:<15} {:<20} {:<25} {:<10}".format(
            "SERVICE", "STATUS", "LAST CHECK", "RESTARTS"), 'cyan'))
        print(colored("-" * 70, 'white'))
        
        for service, data in monitored_services.items():
            status_color = 'green' if data["status"] == "Running" else 'red'
            print("{:<15} {:<20} {:<25} {:<10}".format(
                colored(service, 'white'),
                colored(data["status"], status_color),
                data["last_check"],
                data["restart_count"]
            ))
    
    print(colored("\nPress Ctrl+C to exit dashboard view", 'yellow'))

def add_custom_service():
    clear_screen()
    print_ascii_art()
    
    print(colored("ADD CUSTOM SERVICE", 'green'))
    print(colored("-" * 70, 'white'))
    
    service_name = input(colored("Enter service name: ", 'yellow'))
    if not service_name:
        print(colored("Service name cannot be empty", 'red'))
        input(colored("Press Enter to continue...", 'yellow'))
        return
    
    if service_name in SERVICES_CONFIG:
        print(colored(f"Service {service_name} already exists", 'red'))
        input(colored("Press Enter to continue...", 'yellow'))
        return
    
    service_systemd_name = input(colored("Enter systemd service name (default: same as service name): ", 'yellow'))
    if not service_systemd_name:
        service_systemd_name = service_name
    
    port_str = input(colored("Enter port number (leave empty if not applicable): ", 'yellow'))
    port = int(port_str) if port_str.isdigit() else None
    
    restart_command = input(colored(f"Enter restart command (default: systemctl restart {service_systemd_name}): ", 'yellow'))
    if not restart_command:
        restart_command = f"systemctl restart {service_systemd_name}"
    
    status_command = input(colored(f"Enter status command (default: systemctl status {service_systemd_name}): ", 'yellow'))
    if not status_command:
        status_command = f"systemctl status {service_systemd_name}"
    
    SERVICES_CONFIG[service_name] = {
        "service_name": service_systemd_name,
        "port": port,
        "restart_command": restart_command,
        "status_command": status_command,
    }
    
    print(colored(f"Service {service_name} added successfully", 'green'))
    input(colored("Press Enter to continue...", 'yellow'))

def live_dashboard():
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        while True:
            display_dashboard()
            time.sleep(5)
    except KeyboardInterrupt:
        return

def main_menu():
    signal.signal(signal.SIGINT, signal_handler)
    
    while not stop_event.is_set():
        clear_screen()
        print_ascii_art()
        
        print(colored("MAIN MENU", 'green'))
        print(colored("1. Start Monitoring Service", 'white'))
        print(colored("2. Stop Monitoring Service", 'white'))
        print(colored("3. Check Service Status", 'white'))
        print(colored("4. View Monitoring Dashboard", 'white'))
        print(colored("5. Manually Restart Service", 'white'))
        print(colored("6. Add Custom Service", 'white'))
        print(colored("7. View Log File", 'white'))
        print(colored("8. Exit", 'white'))
        
        choice = input(colored("\nEnter your choice (1-8): ", 'yellow'))
        
        if choice == '1':
            start_monitoring_menu()
        elif choice == '2':
            stop_monitoring_menu()
        elif choice == '3':
            check_status_menu()
        elif choice == '4':
            live_dashboard()
        elif choice == '5':
            manual_restart_menu()
        elif choice == '6':
            add_custom_service()
        elif choice == '7':
            view_log_menu()
        elif choice == '8':
            print(colored("Exiting program...", 'yellow'))
            stop_event.set()
            break
        else:
            print(colored("Invalid choice. Press Enter to continue...", 'red'))
            input()

def start_monitoring_menu():
    clear_screen()
    print_ascii_art()
    
    print(colored("START MONITORING SERVICE", 'green'))
    print(colored("-" * 70, 'white'))
    
    available_services = get_available_services()
    for i, service in enumerate(available_services, 1):
        print(colored(f"{i}. {service}", 'white'))
    
    print(colored("0. Return to Main Menu", 'white'))
    
    try:
        choice = int(input(colored("\nEnter your choice: ", 'yellow')))
        if choice == 0:
            return
        
        if 1 <= choice <= len(available_services):
            service = available_services[choice - 1]
            
            interval = input(colored("Enter check interval in seconds (default: 30): ", 'yellow'))
            interval = int(interval) if interval.isdigit() and int(interval) > 0 else 30
            
            start_monitoring_service(service, interval)
        else:
            print(colored("Invalid choice", 'red'))
    except ValueError:
        print(colored("Please enter a valid number", 'red'))
    
    input(colored("Press Enter to continue...", 'yellow'))

def stop_monitoring_menu():
    clear_screen()
    print_ascii_art()
    
    print(colored("STOP MONITORING SERVICE", 'green'))
    print(colored("-" * 70, 'white'))
    
    if not monitored_services:
        print(colored("No services are currently being monitored", 'yellow'))
    else:
        services = list(monitored_services.keys())
        for i, service in enumerate(services, 1):
            status = monitored_services[service]["status"]
            status_color = 'green' if status == "Running" else 'red'
            print(colored(f"{i}. {service} - ", 'white') + colored(status, status_color))
        
        print(colored("0. Return to Main Menu", 'white'))
        
        try:
            choice = int(input(colored("\nEnter your choice: ", 'yellow')))
            if choice == 0:
                return
            
            if 1 <= choice <= len(services):
                service = services[choice - 1]
                stop_monitoring_service(service)
            else:
                print(colored("Invalid choice", 'red'))
        except ValueError:
            print(colored("Please enter a valid number", 'red'))
    
    input(colored("Press Enter to continue...", 'yellow'))

def check_status_menu():
    clear_screen()
    print_ascii_art()
    
    print(colored("CHECK SERVICE STATUS", 'green'))
    print(colored("-" * 70, 'white'))
    
    available_services = get_available_services()
    for i, service in enumerate(available_services, 1):
        print(colored(f"{i}. {service}", 'white'))
    
    print(colored("0. Return to Main Menu", 'white'))
    
    try:
        choice = int(input(colored("\nEnter your choice: ", 'yellow')))
        if choice == 0:
            return
        
        if 1 <= choice <= len(available_services):
            service = available_services[choice - 1]
            
            print(colored(f"\nChecking status of {service}...", 'yellow'))
            is_running, status_msg = check_service_status(service)
            
            status = "Running" if is_running else "Not running"
            status_color = 'green' if is_running else 'red'
            
            print(colored(f"Status: {status}", status_color))
            print(colored("Details:", 'white'))
            print(status_msg)
        else:
            print(colored("Invalid choice", 'red'))
    except ValueError:
        print(colored("Please enter a valid number", 'red'))
    
    input(colored("\nPress Enter to continue...", 'yellow'))

def manual_restart_menu():
    clear_screen()
    print_ascii_art()
    
    print(colored("MANUALLY RESTART SERVICE", 'green'))
    print(colored("-" * 70, 'white'))
    
    available_services = get_available_services()
    for i, service in enumerate(available_services, 1):
        print(colored(f"{i}. {service}", 'white'))
    
    print(colored("0. Return to Main Menu", 'white'))
    
    try:
        choice = int(input(colored("\nEnter your choice: ", 'yellow')))
        if choice == 0:
            return
        
        if 1 <= choice <= len(available_services):
            service = available_services[choice - 1]
            
            print(colored(f"\nManually restarting {service}...", 'yellow'))
            success = restart_service(service)
            
            if success:
                print(colored(f"Successfully restarted {service}", 'green'))
                
                if service in monitored_services:
                    monitored_services[service]["last_restart"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    monitored_services[service]["restart_count"] += 1
            else:
                print(colored(f"Failed to restart {service}", 'red'))
        else:
            print(colored("Invalid choice", 'red'))
    except ValueError:
        print(colored("Please enter a valid number", 'red'))
    
    input(colored("\nPress Enter to continue...", 'yellow'))

def view_log_menu():
    clear_screen()
    print_ascii_art()
    
    print(colored("VIEW LOG FILE", 'green'))
    print(colored("-" * 70, 'white'))
    
    try:
        with open(log_file, "r") as f:
            log_content = f.readlines()
        
        if not log_content:
            print(colored("Log file is empty", 'yellow'))
        else:
            print(colored("Last 20 log entries:", 'white'))
            for line in log_content[-20:]:
                if "[ERROR]" in line:
                    print(colored(line.strip(), 'red'))
                elif "[WARNING]" in line:
                    print(colored(line.strip(), 'yellow'))
                elif "[SUCCESS]" in line:
                    print(colored(line.strip(), 'green'))
                else:
                    print(colored(line.strip(), 'white'))
    except FileNotFoundError:
        print(colored("Log file does not exist yet", 'yellow'))
    
    input(colored("\nPress Enter to continue...", 'yellow'))

if __name__ == "__main__":
    try:
        if not os.path.exists(log_file):
            with open(log_file, "w") as f:
                f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [INFO] Service monitor started\n")
        
        log_message("Service monitor started", "INFO")
        main_menu()
    except KeyboardInterrupt:
        print(colored("\nProgram terminated by user", 'yellow'))
        stop_event.set()
    except Exception as e:
        print(colored(f"\nAn error occurred: {str(e)}", 'red'))
        log_message(f"Fatal error: {str(e)}", "ERROR")
