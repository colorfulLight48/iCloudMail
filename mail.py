import imaplib
import email
import os
import subprocess
import smtplib
from email.message import EmailMessage
import tempfile
import webbrowser
import os
import email
import shutil 
import mimetypes  # Add this to the top of your file
import json
from datetime import datetime


# Configuration
USER = os.environ.get("EMAIL_ADDRESS")
PASSWORD = os.environ.get("PASSWORD")
SERVER = 'imap.mail.me.com'
SEND_SCRIPT_PATH = "/Users/astro77/mail/script.py"

def connect_mail():
    mail = imaplib.IMAP4_SSL(SERVER)
    mail.login(USER, PASSWORD)
    # select() returns ('OK', [b'Total_Count'])
    status, count_data = mail.select("inbox")
    total_emails = int(count_data[0].decode())
    return mail, total_emails

def resolve_index(idx, total):
    """Converts a potentially negative index into a positive IMAP index."""
    if idx < 0:
        return max(1, total + idx + 1)
    return idx



def list_emails(start_input, end_input):
    mail, total = connect_mail()
    
    # Convert inputs to positive IMAP indices
    idx1 = resolve_index(start_input, total)
    idx2 = resolve_index(end_input, total)
    
    # IMAP fetch requires start:end where start < end
    # We find the min and max to ensure a valid IMAP range
    imap_start = min(idx1, idx2)
    imap_end = max(idx1, idx2)

    status, data = mail.fetch(f"{imap_start}:{imap_end}", '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
    
    # Extract the messages into a list so we can reverse them
    messages = []
    current_idx = imap_start
    for response_part in data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            messages.append((current_idx, msg))
            current_idx += 1
            
    # Reverse the list to show latest first
    messages.reverse()

    print(f"\n--- Showing emails {imap_end} down to {imap_start} ---")
    for idx, msg in messages:
        # Clean up the 'From' and 'Subject' strings for display
        sender = str(msg['From']).strip()
        subject = str(msg['Subject']).strip()
        print(f"[{idx}] From: {sender} | Subject: {subject}")
            
    mail.logout()



def read_email(idx_input):
    mail, total = connect_mail()
    idx = resolve_index(idx_input, total)
    
    # Fetch the full email body
    status, data = mail.fetch(str(idx), '(BODY[])')
    
    if status == 'OK' and data[0]:
        msg = email.message_from_bytes(data[0][1])
        print(f"\n--- Reading Email #{idx} ---")
        print(f"From: {msg['From']}")
        print(f"Subject: {msg['Subject']}\n")
        
        html_content = None
        attachments = []
        
        # 1. Parse parts: Print text, store HTML, and track attachments
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    print(payload.decode(errors='replace'))
            
            elif content_type == "text/html" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    html_content = payload.decode(errors='replace')
                
            elif "attachment" in disposition:
                filename = part.get_filename()
                if filename:
                    attachments.append((filename, part))

    
        
        # ... (inside read_email after parsing html_content)
        
        if html_content:
            print("\n[HTML Content Detected]")
            action = input("Actions: (v)iew, (e)xport, or (s)kip: ").lower().strip()
            
            if action in ['v', 'e']:
                secure = input("Enable security (disable JS)? (y/n): ").lower() != 'n'
                csp_meta = '<meta http-equiv="Content-Security-Policy" content="script-src \'none\';">' if secure else ''
                final_html = csp_meta + html_content

                if action == 'v':
                    # Viewing: Create temp file but DON'T delete on close
                    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html', encoding='utf-8') as f:
                        f.write(final_html)
                        temp_path = f.name
                    
                    print(f"Opening secured={secure} view...")
                    webbrowser.open(f"file://{temp_path}")
                    
                    # After viewing, ask to keep it
                    keep = input("\nView complete. Export this to a permanent file? (y/n): ").lower().strip()
                    if keep == 'y':
                        default_name = f"email_{idx}.html"
                        perm_path = input(f"Save as (default: {default_name}): ").strip() or default_name
                        try:
                            shutil.move(temp_path, perm_path)
                            print(f"Permanent copy saved to: {os.path.abspath(perm_path)}")
                        except Exception as e:
                            print(f"Failed to save permanent copy: {e}")
                    else:
                        os.unlink(temp_path)  # Manually delete if they don't want to keep it
                
                elif action == 'e':
                    # Direct Export: Same as before
                    default_name = f"email_{idx}.html"
                    export_path = input(f"Export filename (default: {default_name}): ").strip() or default_name
                    try:
                        with open(export_path, 'w', encoding='utf-8') as f:
                            f.write(final_html)
                        print(f"File exported to: {os.path.abspath(export_path)}")
                    except Exception as e:
                        print(f"Export failed: {e}")
        
        
        # 3. Handle Attachments
        if attachments:
            print(f"\n--- Attachments found: {len(attachments)} ---")
            for i, (fname, _) in enumerate(attachments):
                print(f"[{i}] {fname}")
            
            print("\nEnter numbers to download (e.g., '0, 2'), 'all', or 'n': ")
            user_input = input(">> ").lower().strip()
            
            to_download = []
            if user_input == 'all':
                to_download = attachments
            elif user_input != 'n' and user_input != '':
                indices = user_input.replace(',', ' ').split()
                for idx_str in indices:
                    if idx_str.isdigit():
                        i = int(idx_str)
                        if 0 <= i < len(attachments):
                            to_download.append(attachments[i])
            
            for filename, part in to_download:
                default_path = os.path.expanduser(f"~/Downloads/{filename}")
                # Use default path for bulk; ask for single
                save_path = default_path if len(to_download) > 1 else (input(f"Save path for {filename} (default: {default_path}): ").strip() or default_path)
                
                try:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    print(f"Saved: {save_path}")
                except Exception as e:
                    print(f"Error saving {filename}: {e}")
    else:
        print(f"Error: Could not find email at index {idx}.")
    
    mail.logout()





DRAFTS_DIR = "drafts"

def save_draft(data):
    if not os.path.exists(DRAFTS_DIR):
        os.makedirs(DRAFTS_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(DRAFTS_DIR, f"draft_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"\n💾 Galactic Systems: Draft saved to {filename}")

def send_mail(draft_data=None):
    # Restore all data structures including attachment paths
    data = draft_data or {
        "to": [], "cc": [], "bcc": [], 
        "subject": "", "fmt": "1", "body": "", "attachments": []
    }
    current_step = "recipients"

    def parse_addrs(prompt, existing):
        default = ", ".join(existing) if existing else ""
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw: return existing
        return [addr.strip() for addr in raw.replace(',', ' ').split() if addr.strip()]

    try:
        # Step 1: Recipients
        data["to"] = parse_addrs("To", data["to"])
        data["cc"] = parse_addrs("Cc", data["cc"])
        data["bcc"] = parse_addrs("Bcc", data["bcc"])
        
        # Step 2: Subject
        current_step = "subject"
        data["subject"] = input(f"Subject [{data['subject']}]: ") or data["subject"]
        
        # Step 3: Format
        current_step = "fmt"
        print("Select Format: 1: Plaintext | 2: HTML")
        data["fmt"] = input(f"Choice [{data['fmt']}]: ") or data["fmt"]

        # Step 4: Body
        current_step = "body"
        print(f"\n--- Enter Content (Ctrl+C to SUBMIT Body) ---")
        # If loading a draft, show the existing body first
        if data["body"]:
            print(f"[Existing Body]:\n{data['body']}\n[Continue typing below]:")
        
        lines = []
        while True:
            lines.append(input())

    except KeyboardInterrupt:
        if current_step == "body":
            # Combine new lines with any existing draft body
            new_content = "\n".join(lines)
            data["body"] = (data["body"] + "\n" + new_content).strip()
            
            print("\n\n[!] Body Captured.")
            confirm = input("Submit to send? (y)es, (s)ave draft, (d)iscard: ").lower().strip()
            if confirm == 's':
                save_draft(data)
                return
            elif confirm == 'd':
                print("🗑️ Discarded.")
                return
            elif confirm != 'y':
                print("Action cancelled. Returning to menu.")
                return
        else:
            print("\n\n[!] Interrupt detected.")
            if input("Save progress as draft? (y/n): ").lower() == 'y':
                save_draft(data)
            return

    # Step 5: Attachments (restored logic)
    current_step = "attachments"
    existing_att = ", ".join(data["attachments"])
    print(f"\nAdd attachments? Current: [{existing_att}]")
    new_paths = input("New Paths (comma/space separated, or Enter to keep current): ").strip()
    if new_paths:
        data["attachments"].extend([p.strip() for p in new_paths.replace(',', ' ').split()])

    # --- SMTP SENDING PROCESS ---
    msg = EmailMessage()
    if data["fmt"] == "2":
        msg.set_content("This is an HTML email. Please use an HTML-compatible client.")
        msg.add_alternative(data["body"], subtype='html')
    else:
        msg.set_content(data["body"])

    msg['Subject'] = data["subject"]
    msg['From'] = USER
    msg['To'] = ", ".join(data["to"])
    if data["cc"]: msg['Cc'] = ", ".join(data["cc"])
    
    # Process Attachments for the email object
    for path in data["attachments"]:
        full_path = os.path.expanduser(path)
        if os.path.isfile(full_path):
            ctype, _ = mimetypes.guess_type(full_path)
            main, sub = (ctype or 'application/octet-stream').split('/', 1)
            try:
                with open(full_path, 'rb') as f:
                    msg.add_attachment(f.read(), maintype=main, subtype=sub, filename=os.path.basename(full_path))
                print(f"Attached: {os.path.basename(full_path)}")
            except Exception as e:
                print(f"Attachment error ({path}): {e}")

    # Combine all recipients for the SMTP envelope
    all_recipients = data["to"] + data["cc"] + data["bcc"]
    
    try:
        with smtplib.SMTP("smtp.mail.me.com", 587) as server:
            server.starttls()
            server.login(USER, PASSWORD)
            server.send_message(msg, to_addrs=all_recipients)
            print(f"🚀 Galactic Systems: Successfully sent to {len(all_recipients)} recipients!")
    except Exception as e:
        print(f"❌ SMTP Error: {e}")
        if input("Save failed email as draft? (y/n): ").lower() == 'y':
            save_draft(data)


def list_drafts():
    # 1. Check if directory exists and has files
    if not os.path.exists(DRAFTS_DIR) or not os.listdir(DRAFTS_DIR):
        print(f"\n[!] Galactic Systems: No drafts found in {DRAFTS_DIR}")
        return

    # 2. Get list of JSON files
    files = [f for f in os.listdir(DRAFTS_DIR) if f.endswith('.json')]
    if not files:
        print("\n[!] Galactic Systems: No valid .json drafts found.")
        return

    print(f"\n{'='*20} GALACTIC DRAFTS {'='*20}")
    for i, filename in enumerate(files):
        # We try to load the file briefly to show the Subject in the list
        try:
            with open(os.path.join(DRAFTS_DIR, filename), "r") as f:
                temp_data = json.load(f)
                subj = temp_data.get("subject", "No Subject")
                dest = ", ".join(temp_data.get("to", [])) or "No Recipient"
                print(f"[{i}] {filename} | To: {dest} | Subj: {subj}")
        except:
            print(f"[{i}] {filename} (Could not parse file)")

    # 3. User Selection
    choice = input("\nSelect index to load (or 'n' to cancel): ").strip().lower()
    
    if choice == 'n' or not choice:
        print("Returning to main menu.")
        return

    try:
        idx = int(choice)
        if 0 <= idx < len(files):
            target_file = os.path.join(DRAFTS_DIR, files[idx])
            
            with open(target_file, "r") as f:
                loaded_data = json.load(f)
            
            print(f"\n📂 Loading Draft: {files[idx]}...")
            
            # 4. Remove the file so it doesn't stay there if we send it
            os.remove(target_file)
            
            # 5. Pass the data back into the send_mail function
            send_mail(loaded_data)
        else:
            print("[!] Invalid index.")
    except ValueError:
        print("[!] Please enter a valid number.")
    except Exception as e:
        print(f"[!] Error loading draft: {e}")

def get_unread_count():
    try:
        mail, _ = connect_mail()
        # Search for messages that do not have the \Seen flag
        status, response = mail.search(None, 'UNSEEN')
        unread_ids = response[0].split()
        count = len(unread_ids)
        mail.logout()
        return count
    except:
        return "?"

def main():
    print(f"\n{'='*40}")
    print(f"🚀 iCLOUD MAIL CLI v2.0")
    print(f"Account: {USER}")
    print(f"Unread Messages: {get_unread_count()}")
    print(f"{'='*40}")

    while True:
        try:
            cmd = input("\n[iCloud] (list/read/send/load/exit): ").lower().strip()
            
            if cmd == "list":
                s = int(input("Start index (e.g. -10): "))
                e = int(input("End index (e.g. -1): "))
                list_emails(s, e)
            elif cmd == "read":
                idx = int(input("Enter index: "))
                read_email(idx)
            elif cmd == "send":
                send_mail()
            elif cmd == "load":
                list_drafts()
            elif cmd == "exit":
                print("Logging out...")
                break
        except ValueError:
            print("⚠️ Invalid input. Use numbers for indices.")
        except KeyboardInterrupt:
            print("\nReturning to main menu...")
            continue 


if __name__ == "__main__":
    main()
