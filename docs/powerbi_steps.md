# Power BI page: step by step

Run `python run_all.py` first. It writes the three tables this page reads.

## 1. Load the tables
1. Open Power BI Desktop. Click **Get data > Text/CSV**.
2. Open `outputs\powerbi_monthly.csv`. Click **Load**.
3. Repeat for `outputs\powerbi_revenue_by_service.csv` and `outputs\powerbi_channels.csv`.

## 2. Check the links between tables
1. Click the **Model view** icon on the left (three linked boxes).
2. There should be a line from `powerbi_monthly[month]` to `month` in each of the other two tables.
3. If a line is missing, drag `month` from `powerbi_monthly` onto `month` in the other table.

## 3. Set number formats
In **Table view**, click a column, then use the **Column tools** ribbon:
- `mql_rate`, `close_rate`, `diag_to_close` and their `_ly` versions: **Percentage**, 1 decimal.
- `revenue`, `revenue_ly`, `revenue_cad`, `revenue_per_client`: **Whole number**, thousands separator on.
- `month_label`: **Sort by column > month** (so months sort in date order, not alphabetically).

## 4. Build the page (Report view)
1. **Title**: Insert > Text box. Type `Zorora Academy: Monthly Business Review`. Below it, a smaller text box: `Reconstructed operating dataset, Jan 2024 to May 2026`.
2. **Month picker**: add a Slicer with `month_label`. In Format > Slicer settings, set **Style: Dropdown** and **Single select: On**. Pick `Nov 2025`.
3. **Four headline cards** (top row): one Card each for `paid_clients`, `revenue`, `close_rate`, `mql_rate`.
4. **Last-year cards** (second row): one Card each for `paid_clients_ly`, `revenue_ly`, `close_rate_ly`, `mql_rate_ly`. Rename each in the Visualizations pane to "Same month last year".
5. **Trend line**: Line chart. X-axis `month`, Y-axis `leads` and `paid_clients`. Right-click `month` in the X-axis well and choose **month** (not Date Hierarchy).
6. **Revenue by service**: Clustered bar chart. Y-axis `service_category`, X-axis `revenue_bdt`.
7. **Stop the month picker filtering the trend line**: click the slicer, then **Format > Edit interactions**. On the line chart, click the **None** icon. Click Edit interactions again to finish.

## 5. Save
**File > Save as** `Zorora_MBR.pbix` in the main `zorora-mbr` folder.

If someone else opens the file and the data does not load: **Transform data > Data source settings > Change Source**, and point each table to their own `outputs` folder.
