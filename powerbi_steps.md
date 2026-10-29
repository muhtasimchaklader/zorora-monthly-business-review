# Power BI page: step by step

Run `python run_all.py` first. It writes the three tables this page reads.
The finished page is saved as `zorora_mbr.pbix` in the main folder.

## 1. Load the tables
1. Open Power BI Desktop. Click **Get data > Text/CSV**.
2. Open `outputs\powerbi_monthly.csv`. Click **Load**.
3. Repeat for `outputs\powerbi_revenue_by_service.csv` and `outputs\powerbi_channels.csv`.

## 2. Check the links between tables
1. Click the **Model view** icon on the left (three linked boxes).
2. There should be a line from `powerbi_monthly[month]` to `month` in each of the other two tables.
3. If a line is missing, drag `month` from `powerbi_monthly` onto `month` in the other table.
   It works like a VLOOKUP: one row per month in `powerbi_monthly`, many rows per month in the others.

## 3. Set number formats
In **Table view** (grid icon on the left), click a column, then use the **Column tools** ribbon:
- `mql_rate`, `close_rate`, `diag_to_close` and their `_ly` versions: **Percentage**, decimal places **1**.
- `revenue`, `revenue_ly`, `revenue_cad`, `revenue_per_client`: **Whole number**, thousands separator on.
- `month`: format **mmm yyyy**. Use `month` everywhere, not `month_label`: Power BI reads
  `month_label` as a date too, so it adds nothing.

## 4. Build the page (Report view)
Always take `month` from the **powerbi_monthly** table (click the **>** next to it in the Data pane).

1. **Title**: Insert > Text box. Type `Zorora Academy: Monthly Business Review`. On the next line, smaller: `Reconstructed operating dataset, Jan 2024 to May 2026`.
2. **Month picker**: Slicer (5th row, 3rd icon: a small table with a funnel). Field: `month` from `powerbi_monthly`. Paintbrush icon > Slicer settings: **Style: Dropdown**, **Single select: On**. Pick November 2025.
3. **This month card**: Card (new) is the **5th row, 1st icon**, marked "123" with a lightning bolt. One card holds several numbers: drag in `paid_clients`, `revenue`, `close_rate`, `mql_rate`. In the Data box, double-click each to rename: Paid clients, Revenue (BDT), Close rate, MQL rate.
4. **Same month last year card**: a second Card (new) with `paid_clients_ly`, `revenue_ly`, `close_rate_ly`, `mql_rate_ly`, renamed "…, last year". Place it under the first.
5. **Trend line**: Line chart (2nd row, 1st icon). X-axis `month`; click the arrow next to it and choose **month**, not Date Hierarchy. Y-axis `leads`. Put `paid_clients` in **Secondary y-axis** so it is not squashed flat. Rename both. Title: Leads and paid clients by month.
6. **Revenue by service**: Clustered bar chart (1st row, 3rd icon). Y-axis `service_category`, X-axis `revenue_bdt`, **both from `powerbi_revenue_by_service`**. Using `revenue` from the monthly table gives every bar the month's total. Title: Revenue by service, selected month.
7. **Stop the month picker filtering the trend line**: click the slicer, then **Format > Edit interactions**. On the line chart, click the **circle with a slash** (None). Leave the cards and bar chart on the filter icon. Click Edit interactions again to finish.

**Check**: November 2025 shows 6 paid clients, 270K, 9.8%, 29.8%; last year 4, 93K, 5.6%, 24.2%; bars 170K, 70K, 30K. October 2025 shows 8 paid clients. The line chart does not change when the month changes.

## 5. Save
**File > Save as** `zorora_mbr.pbix` in the main folder.

If someone else opens the file and the data does not load: **Transform data > Data source settings > Change Source**, and point each table to their own `outputs` folder.

## If something looks wrong
- **Cards show "--" or will not change with the month**: a dot or bar on another chart is selected, and that filters the whole page. Click the dark dot or bar once to release it, or click empty space inside the chart.
- **Cards show one month only and ignore the picker**: open the Filters pane with the card selected and clear any `month` filter there; then check the slicer's `month` comes from `powerbi_monthly`.
- **Line chart shows a single dot or "by Year"**: the month picker is still filtering it (redo step 7), or the X-axis is on Date Hierarchy (step 5).
- **Can't see a chart**: click **Fit to page** (square icon, bottom right next to the zoom %), or use **Format > Selection** to list everything on the page.