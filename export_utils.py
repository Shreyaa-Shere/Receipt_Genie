import pandas as pd
import io
from fpdf import FPDF
from PIL import Image
import tempfile
import os

def export_to_csv(store_info, transaction_details, items):
    # Combine all data into a single DataFrame for CSV
    # This is a simplified approach; real-world might need more structured CSVs
    data = []
    data.append({'Type': 'Store Info', 'Field': 'Name', 'Value': store_info.get('name')})
    data.append({'Type': 'Store Info', 'Field': 'Address', 'Value': store_info.get('address')})
    data.append({'Type': 'Store Info', 'Field': 'Phone', 'Value': store_info.get('phone')})
    data.append({'Type': 'Store Info', 'Field': 'Date', 'Value': store_info.get('date')})

    data.append({'Type': 'Transaction Details', 'Field': 'Total', 'Value': transaction_details.get('total')})
    data.append({'Type': 'Transaction Details', 'Field': 'Tax', 'Value': transaction_details.get('tax')})
    data.append({'Type': 'Transaction Details', 'Field': 'Subtotal', 'Value': transaction_details.get('subtotal')})
    data.append({'Type': 'Transaction Details', 'Field': 'Payment Method', 'Value': transaction_details.get('payment_method')})
    data.append({'Type': 'Transaction Details', 'Field': 'Change', 'Value': transaction_details.get('change')})

    for item in items:
        data.append({
            'Type': 'Item',
            'Field': item.get('name'),
            'Value': f"Qty: {item.get('quantity')}, Price: {item.get('price'):.2f}, Subtotal: {item.get('subtotal'):.2f}, Category: {item.get('category')}"
        })

    df = pd.DataFrame(data)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue().encode('utf-8')

def export_to_excel(store_info, transaction_details, items, pie_data):
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        # Store Info
        store_df = pd.DataFrame({
            'Field': ['Name', 'Address', 'Phone', 'Date'],
            'Value': [store_info.get('name'), store_info.get('address'), store_info.get('phone'), store_info.get('date')]
        })
        store_df.to_excel(writer, sheet_name='Store Info', index=False)

        # Transaction Details
        txn_df = pd.DataFrame({
            'Field': ['Total', 'Tax', 'Subtotal', 'Payment Method', 'Change'],
            'Value': [transaction_details.get('total'), transaction_details.get('tax'), transaction_details.get('subtotal'), transaction_details.get('payment_method'), transaction_details.get('change')]
        })
        txn_df.to_excel(writer, sheet_name='Transaction Details', index=False)

        # Items
        items_df = pd.DataFrame(items)
        if not items_df.empty:
            items_df.to_excel(writer, sheet_name='Items', index=False)
        else:
            empty_df = pd.DataFrame([{'name': 'No items found', 'price': 0, 'quantity': 0, 'category': 'None', 'subtotal': 0}])
            empty_df.to_excel(writer, sheet_name='Items', index=False)

        # Spending by Category
        if pie_data:
            pie_df = pd.DataFrame(pie_data)
            pie_df.to_excel(writer, sheet_name='Spending by Category', index=False)
        else:
            empty_pie_df = pd.DataFrame([{'Category': 'No data', 'Total': 0}])
            empty_pie_df.to_excel(writer, sheet_name='Spending by Category', index=False)

    excel_buffer.seek(0)
    return excel_buffer.getvalue()

def export_to_pdf(store_info, transaction_details, items, fig):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(200, 10, 'Receipt Genie Report', 0, 1, 'C')
    pdf.ln(10)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(200, 10, 'Store Information', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, f"Name: {store_info.get('name')}")
    pdf.multi_cell(0, 5, f"Address: {store_info.get('address')}")
    pdf.multi_cell(0, 5, f"Phone: {store_info.get('phone')}")
    pdf.multi_cell(0, 5, f"Date: {store_info.get('date')}")
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(200, 10, 'Transaction Details', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, f"Total: ${transaction_details.get('total'):.2f}")
    pdf.multi_cell(0, 5, f"Tax: ${transaction_details.get('tax'):.2f}")
    pdf.multi_cell(0, 5, f"Subtotal: ${transaction_details.get('subtotal'):.2f}")
    pdf.multi_cell(0, 5, f"Payment Method: {transaction_details.get('payment_method')}")
    pdf.multi_cell(0, 5, f"Change: ${transaction_details.get('change'):.2f}")
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(200, 10, 'Items', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    if items:
        # Table header
        col_widths = [50, 20, 25, 30, 45]  # Adjust as needed
        headers = ['Name', 'Qty', 'Price', 'Subtotal', 'Category']
        pdf.set_fill_color(200, 200, 200)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 8, header, border=1, align='C', fill=True)
        pdf.ln()
        pdf.set_fill_color(255, 255, 255)
        # Table rows
        for item in items:
            pdf.cell(col_widths[0], 8, str(item.get('name', '')), border=1)
            pdf.cell(col_widths[1], 8, str(item.get('quantity', '')), border=1, align='C')
            pdf.cell(col_widths[2], 8, f"${item.get('price', 0):.2f}", border=1, align='R')
            pdf.cell(col_widths[3], 8, f"${item.get('subtotal', 0):.2f}", border=1, align='R')
            pdf.cell(col_widths[4], 8, str(item.get('category', '')), border=1)
            pdf.ln()
    else:
        pdf.multi_cell(0, 5, 'No items found.')
    pdf.ln(5)

    # Add Plotly chart as image
    if fig:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(200, 10, 'Spending by Category', 0, 1, 'L')
        img_bytes = fig.to_image(format="png", engine="kaleido")
        img = Image.open(io.BytesIO(img_bytes))
        
        # Resize image to fit PDF width while maintaining aspect ratio
        img_width, img_height = img.size
        pdf_width = 180  # Max width for image in PDF
        pdf_height = (img_height / img_width) * pdf_width

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img_file:
            img.save(tmp_img_file.name)
            image_path = tmp_img_file.name
        
        # Center the image
        x_coordinate = (pdf.w - pdf_width) / 2
        pdf.image(image_path, x=x_coordinate, w=pdf_width, h=pdf_height)
        os.remove(image_path) # Clean up the temporary file

    pdf_output = pdf.output(dest='S').encode('latin-1') # Output as bytes
    return pdf_output 