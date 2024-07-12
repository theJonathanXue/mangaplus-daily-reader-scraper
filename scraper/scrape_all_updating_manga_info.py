import requests
import psycopg2
from bs4 import BeautifulSoup

'''
This script populates our database for the first time with all the ongoing manga series and their latest chapter
'''

# Database connection details
DB_HOST = 'viaduct.proxy.rlwy.net'
DB_PORT = 46503
DB_NAME = 'railway'
DB_USER = 'postgres'
DB_PASSWORD = 'QlArEMoISGqpJYAXbyRvFnHiOQVZyqwz'

# Connect to the PostgreSQL database
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    print("Connected to the database successfully")
except Exception as e:
    print(f"Error connecting to the database: {e}")
    exit(1)

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'}

# Scrape data
session = requests.Session()
url = 'https://mangaplus.shueisha.co.jp/manga_list/updated'
response = session.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

# Find all the manga titles on the webpage
manga_list = soup.find_all('a', class_='AllTitle-module_allTitle_1CIUC')

# Loop through each manga title and get data
for manga in manga_list:
    manga_url = manga['href']
    manga_response = session.get(manga_url, headers=headers)
    # Get each manga's html
    manga_soup = BeautifulSoup(manga_response.text, 'html.parser')

    # Parse every field we are interest in
    title = manga_soup.find('h1', class_='TitleDetailHeader-module_title_Iy33M' ).text
    cover_src = manga_soup.find('img', class_='TitleDetailHeader-module_coverImage_3rvaT' ).src

    # get the last chapter (which is the latest chapter) and get its value
    latest_chapter_comment_href = manga_soup.find_all('a', class_='ChapterListItem-module_commentContainer_1P6qt')[-1]['href']

    # Get the value by splitting by the href (ex: href="/titles/100282")
    latest_chapter_value = latest_chapter_comment_href.split('/')[-1]
    latest_chapter_src = "https://mangaplus.shueisha.co.jp/viewer/" + latest_chapter_value
    latest_chapter_date = manga_soup.find('p', class_='ChapterListItem-module_date_alreadyRead_31MGZ').text

    # Get a string containing when the next chapter will arrive (Ex: New chapter arrives on Friday, Jul 19, 11:00)
    next_chapter_date = manga_soup.find('p.TitleDetail-module_updateInfo_2MITq > span').text

    # No need for regular expressions since we know that there will always be a unique day of the week in the string we are checking
    def find_day_of_week(text):
        days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in days_of_week:
            if day in text.lower():
                return day
        return None

    # Get the day of the week chapters are updated
    update_day_of_week = find_day_of_week(next_chapter_date)

    # Store data in PostgreSQL
    cursor.execute("""
        INSERT INTO manga_list (title, cover_src, latest_chapter_src, update_day_of_week)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (title) DO UPDATE SET
            cover_src = EXCLUDED.img_src,
            latest_chapter_src = EXCLUDED.latest_chapter_src,
            update_day_of_week = EXCLUDED.update_day_of_week;
    """, (title, cover_src, latest_chapter_src, update_day_of_week))

    # just test one for now
    break

conn.commit()
cursor.close()
conn.close()
