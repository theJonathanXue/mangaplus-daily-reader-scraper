import psycopg2
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

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
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")  # This is important for some versions of Chrome

    # Set path to Chrome binary
    chrome_options.binary_location = "/opt/chrome/chrome-linux64/chrome"

    # Set path to ChromeDriver
    chrome_service = ChromeService(executable_path="/opt/chromedriver/chromedriver-linux64/chromedriver")

    # Set up driver
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    # Connect to the database
    conn, cursor = connect_to_db()
    
    try:
        search_url = 'https://mangaplus.shueisha.co.jp/updates'
        driver.get(search_url)

        # Wait until all manga titles are loaded
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, 'UpdatedTitle-module_titleWrapper_2EQIT'))
        )

        # Find all manga titles on the webpage
        manga_list = driver.find_elements(By.CLASS_NAME, 'UpdatedTitle-module_titleWrapper_2EQIT')
        print("manga_list: ", manga_list)
        # Loop through each manga title
        title_src_list = []
        for manga in manga_list:
            title_src = manga.get_attribute('href') 

            # To find which titles were updated today, we check if it has a specific a tag as a child element
            try:
                manga.find_element(By.CLASS_NAME, "UpdatedTitle-module_upLabel_3afXn")
                print("manga: ", manga)
                title_src_list.append(title_src)
            except NoSuchElementException:
                # We can break since the updates are ordered
                # Sike cannot because of completed series that are updated to be read on the app only
                continue
        
        print("title_src_list: ", title_src_list)
        
        # Now go to each manga title's page and get the data we want for our database
        for title_src in title_src_list:
            # Get manga details page
            driver.get(title_src)

            # Wait until manga details are loaded
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'TitleDetailHeader-module_title_Iy33M'))
            )
            
            # Parse manga details
            # For every manga we must find the title, cover_src, latest_chapter_src, and latest_chapter_date
            # The update_day_of_week is not mandatory
            # We still scrape everything incase there is a new series that we do not have in our DB yet
            try:
                title = driver.find_element(By.CLASS_NAME, 'TitleDetailHeader-module_title_Iy33M').text.strip()
                cover_src = driver.find_element(By.CLASS_NAME, 'TitleDetailHeader-module_coverImage_3rvaT').get_attribute('src')
    
                # Get latest chapter details
                latest_chapter_comment_href = driver.find_elements(By.CLASS_NAME, 'ChapterListItem-module_commentContainer_1P6qt')[-1].get_attribute('href')
                latest_chapter_value = latest_chapter_comment_href.split('/')[-1]
                latest_chapter_src = f"https://mangaplus.shueisha.co.jp/viewer/{latest_chapter_value}"
                
                latest_chapter_date = driver.find_elements(By.CLASS_NAME, 'ChapterListItem-module_date_xe1XF')[-1].text.strip()
                
                # Get update day of the week
                try:
                    next_chapter_date_p = driver.find_element(By.CLASS_NAME, 'TitleDetail-module_updateInfo_2MITq')
                    next_chapter_date = next_chapter_date_p.find_element(By.TAG_NAME, "span").text.strip()
                    update_day_of_week = find_day_of_week(next_chapter_date)
                except:
                    # print(No update_day_of_week information, that's OK
                    update_day_of_week = "not_explicit"
                
                print("title: ", title)
                
                print("title_src: ", title_src)
            
                print("latest_chapter_date: ", latest_chapter_date)
                
                print("latest_chapter_src: ", latest_chapter_src)
                
                # Store data in PostgreSQL
                cursor.execute("""
                    INSERT INTO manga_list (title, cover_src, latest_chapter_src, update_day_of_week, title_src, latest_chapter_date)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (title) DO UPDATE SET
                        cover_src = EXCLUDED.cover_src,
                        latest_chapter_src = EXCLUDED.latest_chapter_src,
                        update_day_of_week = EXCLUDED.update_day_of_week,
                        title_src = EXCLUDED.title_src,
                        latest_chapter_date = EXCLUDED.latest_chapter_date
                """, (title, cover_src, latest_chapter_src, update_day_of_week, title_src, latest_chapter_date))

            except NoSuchElementException as e:
                print(f"Error finding elements on manga details page: {e}")
                print(f"Skipping manga with title_src: {title_src}")
                continue
            except TimeoutException as e:
                print(f"Timeout waiting for element: {e}")
                print(f"Skipping manga with title_src: {title_src}")
                continue
            except Exception as e:
                print(f"Unexpected error: {e}")
                print(f"Skipping manga with title_src: {title_src}")
                continue

        # Commit changes and close cursor and connection
        conn.commit()
        print("Committed to the database successfully")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()  # Rollback changes if any error occurs
        raise

    finally:
        cursor.close()
        conn.close()
        # Close the browser
        driver.quit()

# Entry point
if __name__ == "__main__":
    scrape_manga_data()
