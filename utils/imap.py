# MCacheBox 
# Copyright (c) 2026 Tito de Barros Junior 
# Licensed under the MIT License

from PySide6.QtWidgets import QApplication, QTreeWidgetItem, QHeaderView
from PySide6.QtCore import Qt
import imaplib
import email
import os
from email.header import decode_header
from email.utils import parsedate_to_datetime
import unicodedata
import socket
import traceback

# IMAP OR filter (many words)
def or_chain(field, words):
    if not words:
        return None

    words = [remove_accents(w) for w in words]
    expr = f'{field} "{words[0]}"'

    for w in words[1:]:
        expr = f'(OR {expr} {field} "{w}")'

    return expr

def remove_accents(text):
    return unicodedata.normalize('NFKD', text)\
           .encode('ascii', 'ignore')\
           .decode('ascii')

def extract_words(lst=None, edtLn=None) -> list[str]:
    try:
        if lst is not None:
             return [lst.item(i).text().lower() for i in range(lst.count())]

        if edtLn is not None:
            return edtLn.text().split()
        
        return ["there was no response"]
    except TypeError as e:
        print(f'error: {e}')
        return ["there was no response"]

def fetch_grouped_positions(server_imap,
                            cbxPreFilter=None,
                            progressBar=None,
                            show_message=None,
                            btnClearList=None, 
                            lstPositionsConfig=None,
                            lstDomainsConfig=None,
                            lstExcludedTermsConfig=None,
                            lstWorkModeConfig=None,
                            edtCriteria=None,
                            edtAccount=None,
                            lblRetrievedEmails=None,
                            cbxStarred=None,
                            my_positions=None,
                            max_emails=10,
                            treeMailResponse=None):
    
    # credentials
    PASS = os.environ.get("EMAIL_PASS")
    USER = edtAccount.text().strip()
    
    if not edtAccount:
        show_message("❌ Error: Email account not specified.",10) # type: ignore
        return
    
    if not PASS:
        show_message("❌ Error: The environment variable 'EMAIL_PASS' was not found.",10) # type: ignore
        return

    try:
        imap_server = imaplib.IMAP4_SSL(server_imap)
        imap_server.login(USER, PASS)
        imap_server.select("INBOX")

        # recovering words od components
        CRITERIA_WORDS = [remove_accents(w.lower()) for w in extract_words(None,edtCriteria)]
        DOMAIN_WORDS = [remove_accents(w.lower()) for w in extract_words(lstDomainsConfig)]
        JOB_WORDS = [remove_accents(w.lower()) for w in extract_words(lstPositionsConfig)]
        NEGATIVE_WORDS = [remove_accents(w.lower()) for w in extract_words(lstExcludedTermsConfig)]
        JOB_MODES = [remove_accents(w.lower()) for w in extract_words(lstWorkModeConfig)]

        # Configuring IMAP email rules
        subject_filter = or_chain("SUBJECT", ["vagas","oportunidades","emprego","contratando","trabalhe","trabalho"])
        domain_filter = or_chain("FROM", DOMAIN_WORDS)

        criteria = []
        
        if subject_filter:
            criteria.append(subject_filter)

        if domain_filter:
            criteria.append(domain_filter)

        query = remove_accents(" ".join(criteria))
        
        starred_filter = "FLAGGED" if cbxStarred.isChecked() else "UNFLAGGED"
        
        # pre_filter: quick IMAP check to discard irrelevant emails
        if cbxPreFilter.isChecked(): # type: ignore
            status, dados_busca = imap_server.search(
                None,
                starred_filter,
                query
            )
        else:
            status, dados_busca = imap_server.search(
                None,
                starred_filter,
                "ALL"
            )
        
        MAX_EMAILS = max_emails
        ids_emails = dados_busca[0].split()
        ids_emails = ids_emails[-MAX_EMAILS:]

        show_message(f"\n--- 🚀 Analisyng {len(ids_emails)} emails on server ---\n",10) # type: ignore
        total_counter = 0

        if progressBar:
            progressBar.setMaximum(len(ids_emails))
            progressBar.setValue(0)

        with open("REMOTE_JOBS.txt", "a", encoding="utf-8") as file:
            for i, id_obj in enumerate(ids_emails, start=1):
                if progressBar:
                    progressBar.setValue(i)
                    QApplication.processEvents()
                
                status, email_data = imap_server.fetch(
                    id_obj,
                    "(BODY.PEEK[])"
                )

                for response in email_data:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        # ---------------- date ----------------
                        raw_date = msg.get("Date")

                        if raw_date:
                            try:
                                email_date = parsedate_to_datetime(raw_date)
                                formated_date = email_date.strftime("%d/%m/%Y %H:%M")
                            except:
                                formated_date = "invalid date"
                        else:
                            formated_date = "no date"

                        # ---------------- subject | topic ----------------
                        subject_raw = msg.get("Subject")

                        if subject_raw:
                            decoded = decode_header(subject_raw)[0]
                            topic = (
                                decoded[0].decode(decoded[1] if decoded[1] else "utf-8")
                                if isinstance(decoded[0], bytes)
                                else decoded[0]
                            )
                        else:
                            topic = "(without subject)"

                        # ---------------- email body ----------------
                        body = ""

                        if msg.is_multipart():
                            for part in msg.walk():
                                ctype = part.get_content_type()
                                disp = str(part.get_content_disposition())
                                if ctype in ["text/plain", "text/html"] and "attachment" not in disp:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body += payload.decode(errors="ignore")
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode(errors="ignore")

                        full_content = remove_accents((topic + " " + body).lower())

                        # ---------------- filters ----------------
                        criteria_match = any(t in full_content for t in CRITERIA_WORDS) if CRITERIA_WORDS else False
                        domain_match = any(t in full_content for t in DOMAIN_WORDS) if DOMAIN_WORDS else False
                        mode_match = any(t in full_content for t in JOB_MODES) if JOB_MODES else False
                        negative_match = any(t in full_content for t in NEGATIVE_WORDS) if NEGATIVE_WORDS else False
                        job_match = any(t in full_content for t in JOB_WORDS) if JOB_WORDS else False
                        job_match_words = [t for t in JOB_WORDS if t in full_content]

                        # ---------------- filter application ----------------
                        if job_match and (not edtCriteria.text().strip() or criteria_match) and not negative_match and (domain_match or mode_match):
                            total_counter += 1
                            header = f"📩 [{formated_date}] {topic}\n"
                            remetente = f"   De: {msg.get('From')}\n"
                            details = ""
                            
                            for job in job_match_words:
                                details += f"      [+] Vaga Identificada: {job.upper()}\n"

                            separator = "   " + "-" * 60 + "\n"
                            bloco_final = header + remetente + details + separator

                            file.write(bloco_final)

                            if treeMailResponse is not None:
                                header = treeMailResponse.header()
                                header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                                header.setSectionResizeMode(1, QHeaderView.Stretch)
                                header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

                                item = QTreeWidgetItem(treeMailResponse)
                                item.setText(0, msg.get('From'))
                                item.setText(1, topic)
                                item.setText(2, formated_date)
                                item.setData(0, Qt.UserRole, id_obj)
                                item.setData(1, Qt.UserRole, topic)
                                item.setData(2, Qt.UserRole, body)
        
        btnClearList.setEnabled(True) # type: ignore
        imap_server.logout()
        show_message(f"--- ✅ END: {(total_counter)} relevant emails saved in REMOTE_JOBS.txt ---",30) # type: ignore
        lblRetrievedEmails.setText(f'retrieved emails: {str(total_counter)}')
    except imaplib.IMAP4.error as e:
        show_message(f"❌ IMAP specified error: {e}",20) # type: ignore
        show_message(f"   Code: {e.args}",10) # type: ignore
        traceback.print_exc()
    except socket.gaierror as e:
        show_message(f"❌ DNS/network error: {e}",10) # type: ignore

    except ConnectionRefusedError:
        show_message("❌ Refused connection - 993 port bloqued?",10) # type: ignore
    except Exception as e:
        show_message(f"❌ Unexpected error: {type(e).__name__}: {e}",10) # type: ignore
        traceback.print_exc()