import os
from Bio import Entrez
import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 환경 변수 설정
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PW = os.getenv('GMAIL_PASSWORD')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
RECEIVER_EMAIL = GMAIL_USER 

def get_latest_paper_details():
    Entrez.email = GMAIL_USER
    # 검색 쿼리: Radiology 저널의 최신 논문
    query = 'Radiology[Journal] AND "last 30 days"[dp]'
    handle = Entrez.esearch(db="pubmed", term=query, sort="relevance", retmax=1)
    record = Entrez.read(handle)
    id_list = record["IdList"]
    
    if not id_list:
        return None
    
    pmid = id_list[0]
    fetch_handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
    records = Entrez.read(fetch_handle)
    article_data = records['PubmedArticle'][0]
    medline = article_data['MedlineCitation']['Article']
    
    # 1. 제목 및 초록
    title = medline.get('ArticleTitle', 'No Title')
    abstract_list = medline.get('Abstract', {}).get('AbstractText', [])
    abstract = " ".join([str(text) for text in abstract_list])
    
    # 2. 저자 전원 추출
    authors = []
    for auth in medline.get('AuthorList', []):
        authors.append(f"{auth.get('LastName', '')} {auth.get('Initials', '')}")
    author_text = ", ".join(authors) if authors else "Unknown"
    
    # 3. DOI 정보 추출
    doi = "N/A"
    article_ids = article_data['PubmedData'].get('ArticleIdList', [])
    for aid in article_ids:
        if aid.attributes.get('IdType') == 'doi':
            doi = str(aid)
            break
            
    # 4. 저널 정보 및 날짜
    journal = medline['Journal'].get('Title', 'Unknown Journal')
    pub_date = medline['Journal']['JournalIssue']['PubDate']
    date_str = f"{pub_date.get('Year', 'N/A')} {pub_date.get('Month', '')}"
    
    return {
        "title": title,
        "abstract": abstract,
        "authors": author_text,
        "journal": journal,
        "date": date_str,
        "pmid": pmid,
        "doi": doi,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "doi_url": f"https://doi.org/{doi}" if doi != "N/A" else "#"
    }

def summarize_paper(abstract):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional medical radiologist. Summarize the following abstract in 3 professional bullet points (Objective, Findings, Clinical Implication) in English."},
            {"role": "user", "content": abstract}
        ]
    )
    return response.choices[0].message.content

def send_mail(info, summary):
    # HTML 메일 본문 구성 (가독성 및 이미지 효과)
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="https://pubmed.ncbi.nlm.nih.gov/images/pubmed-logo.pdf.png" alt="PubMed Logo" style="width: 150px;">
                <h2 style="color: #0071bc;">Today's Radiology Pick</h2>
            </div>
            
            <h3 style="color: #2c3e50;">{info['title']}</h3>
            
            <p><strong>Authors:</strong> {info['authors']}</p>
            <p><strong>Journal:</strong> <i>{info['journal']}</i> ({info['date']})</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-left: 5px solid #0071bc; margin: 20px 0;">
                <h4 style="margin-top: 0;">🔬 AI Summary</h4>
                <div style="white-space: pre-wrap;">{summary}</div>
            </div>
            
            <p><strong>PMID:</strong> {info['pmid']} | <strong>DOI:</strong> {info['doi']}</p>
            
            <div style="margin-top: 30px; text-align: center;">
                <a href="{info['pubmed_url']}" style="background-color: #0071bc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-right: 10px;">View on PubMed</a>
                <a href="{info['doi_url']}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View via DOI</a>
            </div>
            
            <hr style="margin-top: 30px;">
            <p style="font-size: 12px; color: #888;">This is an automated research summary for Dr. YoungHan.</p>
        </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['Subject'] = f"Radiology Update: {info['title'][:60]}..."
    msg['From'] = GMAIL_USER
    msg['To'] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_content, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PW)
        server.send_message(msg)

if __name__ == "__main__":
    print("Fetching paper info...")
    info = get_latest_paper_details()
    
    if info:
        print("Generating summary...")
        summary = summarize_paper(info['abstract'])
        
        print("Sending HTML email...")
        send_mail(info, summary)
        print("Success!")
    else:
        print("No papers found.")
