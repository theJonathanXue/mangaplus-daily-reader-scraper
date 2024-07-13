import requests
import psycopg2
import os
from bs4 import BeautifulSoup

# Database configuration
db_config = {
    'host': os.getenv('PGHOST'),
    'user': os.getenv('PGUSER'),
    'password': os.getenv('PGPASSWORD'),
    'database': os.getenv('PGDATABASE'),
    'port': os.getenv('PGPORT')
}

# Function to connect to PostgreSQL
def connect_to_db():
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        print("Connected to the database successfully")
        return conn, cursor
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        raise

# Function to find day of the week
def find_day_of_week(text):
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in days_of_week:
        if day in text.lower():
            return day
    return None

# Main scraping function
def scrape_manga_data():
    # Connect to the database
    conn, cursor = connect_to_db()

    # HTTP headers
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'}

    # Session for making HTTP requests
    session = requests.Session()
    session.verify = False 

    # URL to scrape
    url = 'https://mangaplus.shueisha.co.jp/manga_list/updated'

    try:
        # Make the initial request to get manga list page
        response = session.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for bad responses

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all manga titles on the webpage
        manga_list = soup.find_all('a', class_='AllTitle-module_allTitle_1CIUC')

        # Loop through each manga title and get data
        for manga in manga_list:
            title_src = manga['href']

            # Get manga details page
            manga_response = session.get(title_src, headers=headers)
            manga_soup = BeautifulSoup(manga_response.text, 'html.parser')

            # Parse manga details
            title = manga_soup.find('h1', class_='TitleDetailHeader-module_title_Iy33M').text.strip()
            cover_src = manga_soup.find('img', class_='TitleDetailHeader-module_coverImage_3rvaT')['src']

            # Get latest chapter details
            latest_chapter_comment_href = manga_soup.find_all('a', class_='ChapterListItem-module_commentContainer_1P6qt')[-1]['href']
            latest_chapter_value = latest_chapter_comment_href.split('/')[-1]
            latest_chapter_src = f"https://mangaplus.shueisha.co.jp/viewer/{latest_chapter_value}"
            latest_chapter_date = manga_soup.find('p', class_='ChapterListItem-module_date_alreadyRead_31MGZ').text.strip()

            # Get update day of the week
            next_chapter_date = manga_soup.find('p.TitleDetail-module_updateInfo_2MITq > span').text.strip()
            update_day_of_week = find_day_of_week(next_chapter_date)

            # Store data in PostgreSQL
            cursor.execute("""
                INSERT INTO manga_list (title, cover_src, latest_chapter_src, update_day_of_week, title_src)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (title) DO UPDATE SET
                    cover_src = EXCLUDED.cover_src,
                    latest_chapter_src = EXCLUDED.latest_chapter_src,
                    update_day_of_week = EXCLUDED.update_day_of_week,
                    title_src = EXCLUDED.title_src
            """, (title, cover_src, latest_chapter_src, update_day_of_week, title_src))

        # Commit changes and close cursor and connection
        conn.commit()
        cursor.close()
        conn.close()

        print("Scraping and database update completed successfully.")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()  # Rollback changes if any error occurs
        cursor.close()
        conn.close()
        raise

# Entry point
if __name__ == "__main__":
    scrape_manga_data()
