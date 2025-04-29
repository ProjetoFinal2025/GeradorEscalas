# core/services/pdf_exports.py
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io

def gerar_pdf_escala(escala):
    militares_info = escala.militares_info.select_related('militar').order_by('ordem_semana')
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Militares da Escala: {escala}", styles['Title']))
    elements.append(Spacer(1, 20))

    data = [["NIM", "Posto", "Nome", "Ordem Semana", "Ordem FDS"]]
    for info in militares_info:
        militar = info.militar
        data.append([
            str(militar.nim).zfill(8),
            militar.posto,
            militar.nome,
            info.ordem_semana,
            info.ordem_fds,
        ])

    table = Table(data, colWidths=[70, 70, 150, 60, 60])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('FONTNAME', (0,0),(-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0),(-1,0),12),
        ('BACKGROUND',(0,1),(-1,-1),colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
