import streamlit as st
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Install Playwright browsers (required for deployment)
os.system("playwright install chromium")

# Streamlit App Title
st.title("Multi-County Auction Scraper")

# Counties to scrape
COUNTIES = [
    "Madison",
    "Hocking",
    "Union",
    "Delaware",
    "Fairfield",
    "Pickaway",
    "Licking",
    "Franklin"
]

# User Input for Auction Date Range
st.subheader("Enter the Auction Date Range")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("From Date")
with col2:
    end_date = st.date_input("To Date")

# County Selection
st.subheader("Select Counties to Scrape")
selected_counties = st.multiselect(
    "Choose counties (or leave empty to scrape all)",
    COUNTIES,
    default=COUNTIES
)

# Thread settings
max_workers = st.slider("Number of Concurrent Workers", min_value=1, max_value=10, value=5)

run_button = st.button("Run Scraper")

# Thread-safe progress tracking
progress_lock = threading.Lock()
progress_data = {"completed": 0, "total": 0, "results": []}

def scrape_section_pages(page, section_id, page_input_id, max_pages_id):
    """
    Scrapes all pages within a specific section (Waiting, Running, or Closed).
    Returns list of auction data from all pages in that section.
    """
    data_list = []

    # Find the total number of pages in this section
    max_pages_element = page.locator(max_pages_id)
    if max_pages_element.count() == 0:
        return data_list

    try:
        max_pages = int(max_pages_element.inner_text().strip())
    except:
        return data_list

    # Loop through all pages in this section
    for current_page in range(1, max_pages + 1):
        # Locate auction details in this section
        auction_details = page.locator(f'#{section_id} .AUCTION_DETAILS')
        count = auction_details.count()

        if count == 0:
            break

        # Extract data from each auction detail block
        for i in range(count):
            try:
                current_detail = auction_details.nth(i)

                # Extract table data
                table_rows = current_detail.locator('table.ad_tab tr')
                row_count = table_rows.count()

                auction_data = {}
                for j in range(row_count):
                    try:
                        label = table_rows.nth(j).locator('th.AD_LBL').inner_text().strip(":")
                        value = table_rows.nth(j).locator('td.AD_DTA').inner_text().strip()
                        auction_data[label] = value
                    except:
                        continue

                # Extract 'Auction Starts' from the stats section
                try:
                    auction_stats = page.locator(f'#{section_id} .AUCTION_STATS').nth(i)
                    auction_starts = auction_stats.locator('.ASTAT_MSGB').inner_text().strip()
                except:
                    auction_starts = ""

                # Only add if we have meaningful data
                if auction_data:
                    data_list.append({
                        "auction_data": auction_data,
                        "auction_starts": auction_starts
                    })
            except Exception as e:
                continue

        # Navigate to next page if not on last page
        if current_page < max_pages:
            try:
                page_input = page.locator(page_input_id)
                if page_input.count() > 0:
                    page_input.fill(str(current_page + 1))
                    page_input.press("Enter")
                    time.sleep(3)
                    page.wait_for_load_state('networkidle')
            except:
                break

    return data_list

def scrape_single_auction(county, date):
    """Scrapes auction data for a specific county and date from all sections."""
    with sync_playwright() as p:
        try:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": f"https://{county.lower()}.sheriffsaleauction.ohio.gov/"
                }
            )
            page = context.new_page()

            # Format the date for the URL
            formatted_date = date.strftime('%m/%d/%Y')
            url = f"https://{county.lower()}.sheriffsaleauction.ohio.gov/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={formatted_date}"

            # Navigate to the page
            page.goto(url, timeout=60000)
            page.wait_for_load_state('networkidle')
            time.sleep(5)

            all_data = []

            # Scrape all three sections
            sections = [
                ("Area_W", "#curPWA", "#maxWA", "Waiting"),  # Auctions Waiting
                ("Area_R", "#curPRA", "#maxRA", "Running"),  # Running Auctions
                ("Area_C", "#curPCA", "#maxCA", "Closed")    # Closed/Canceled
            ]

            for section_id, page_input_id, max_pages_id, section_name in sections:
                section_data = scrape_section_pages(page, section_id, page_input_id, max_pages_id)

                # Add section name and format data
                for item in section_data:
                    auction_data = item["auction_data"]
                    all_data.append({
                        "County": county,
                        "Auction Date": formatted_date,
                        "Section": section_name,
                        "Case Status": auction_data.get("Case Status", ""),
                        "Case #": auction_data.get("Case #", ""),
                        "Parcel ID": auction_data.get("Parcel ID", ""),
                        "Property Address": auction_data.get("Property Address", ""),
                        "City, ZIP": auction_data.get("", ""),
                        "Appraised Value": auction_data.get("Appraised Value", ""),
                        "Opening Bid": auction_data.get("Opening Bid", ""),
                        "Deposit Requirement": auction_data.get("Deposit Requirement", ""),
                        "Auction Starts": item["auction_starts"]
                    })

            browser.close()

            if all_data:
                return pd.DataFrame(all_data)
            else:
                return None

        except Exception as e:
            return None

def scrape_with_progress(county, date):
    """Wrapper function for threaded scraping with progress tracking."""
    result = scrape_single_auction(county, date)

    with progress_lock:
        progress_data["completed"] += 1
        if result is not None and not result.empty:
            progress_data["results"].append({
                "county": county,
                "date": date,
                "count": len(result),
                "data": result
            })

    return {
        "county": county,
        "date": date,
        "data": result
    }

def scrape_all_counties_dates(counties, start_date, end_date, max_workers):
    """Scrapes all counties and dates using multiple threads."""
    # Validate date range
    if start_date > end_date:
        st.error("❌ 'From Date' must be before or equal to 'To Date'")
        return None

    # Generate list of dates
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += timedelta(days=1)

    # Create tasks (county, date pairs)
    tasks = [(county, date) for county in counties for date in date_list]
    total_tasks = len(tasks)

    st.info(f"📅 Scraping {len(counties)} counties across {len(date_list)} date(s)")
    st.info(f"🔧 Total tasks: {total_tasks} | Using {max_workers} concurrent workers")

    # Initialize progress tracking
    progress_data["completed"] = 0
    progress_data["total"] = total_tasks
    progress_data["results"] = []

    # Progress bar and status
    overall_progress = st.progress(0)
    status_text = st.empty()
    results_placeholder = st.empty()

    # Execute tasks with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_with_progress, county, date): (county, date)
                   for county, date in tasks}

        for future in as_completed(futures):
            county, date = futures[future]

            # Update progress
            with progress_lock:
                completed = progress_data["completed"]
                progress = completed / total_tasks
                overall_progress.progress(progress)
                status_text.text(f"Progress: {completed}/{total_tasks} tasks completed")

                # Show summary of results so far
                if progress_data["results"]:
                    summary = pd.DataFrame([
                        {"County": r["county"], "Date": r["date"].strftime('%m/%d/%Y'), "Entries": r["count"]}
                        for r in progress_data["results"]
                    ])
                    results_placeholder.dataframe(summary)

    status_text.text(f"✅ All {total_tasks} tasks completed!")

    # Combine all results
    if progress_data["results"]:
        all_dataframes = [r["data"] for r in progress_data["results"]]
        combined_df = pd.concat(all_dataframes, ignore_index=True)

        # Sort by County and then by Date
        combined_df = combined_df.sort_values(by=["County", "Auction Date"])

        return combined_df
    else:
        return None

# Run Scraper if Button is Pressed
if run_button:
    if not selected_counties:
        st.error("❌ Please select at least one county")
    else:
        st.info("🚀 Starting the multi-county scraping process...")
        df = scrape_all_counties_dates(selected_counties, start_date, end_date, max_workers)

        if df is not None and not df.empty:
            # Split and Clean Data
            df[['City', 'ZIP']] = df['City, ZIP'].str.split(',', expand=True)
            df['City'] = df['City'].str.strip()
            df['ZIP'] = df['ZIP'].str.strip()
            df = df.drop(columns=['City, ZIP'])
            df['ZIP'] = df['ZIP'].str[:5]

            # Display Results
            st.success(f"✅ Scraping completed! Total entries: {len(df)}")

            # Show summary by county
            st.subheader("Summary by County and Section")
            county_summary = df.groupby(['County', 'Section']).size().reset_index(name='Total Entries')
            st.dataframe(county_summary)

            # Show full data
            st.subheader("All Auction Data")
            st.dataframe(df)

            # Download Button
            st.download_button(
                label="📥 Download CSV",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name=f'auctions_{start_date.strftime("%Y%m%d")}_to_{end_date.strftime("%Y%m%d")}.csv',
                mime='text/csv'
            )
        else:
            st.warning("⚠️ No data available for the selected counties and date range.")
