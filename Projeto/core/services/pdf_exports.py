# core/services/pdf_exports.py
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io
import logging
from django.db.models import Q
from ..models import ConfiguracaoUnidade, EscalaMilitar

logger = logging.getLogger(__name__)

def gerar_pdf_escala(escala):
    try:
        militares_info = (EscalaMilitar.objects
                         .filter(escala=escala)
                         .select_related("militar")
                         .order_by("ordem"))

        if not militares_info.exists():
            logger.warning(f"Nenhum militar encontrado para a escala {escala.pk}")
            return None

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)

        styles = getSampleStyleSheet()
        elements = []

        # Obter nome da unidade e subunidade
        config = ConfiguracaoUnidade.objects.first()
        if config:
            if config.nome_subunidade:
                nome_cabecalho = f"{config.nome_unidade} - {config.nome_subunidade}"
            else:
                nome_cabecalho = config.nome_unidade
        else:
            nome_cabecalho = "Unidade Militar"
            logger.warning("Configuração da unidade não encontrada")

        # Adicionar cabeçalho com nome da unidade e subunidade
        elements.append(Paragraph(nome_cabecalho, styles['Title']))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"Militares da Escala: {escala}", styles['Heading1']))
        elements.append(Spacer(1, 20))

        data = [["NIM", "Posto", "Nome", "Ordem"]]
        for info in militares_info:
            militar = info.militar
            data.append([
                str(militar.nim).zfill(8),
                militar.posto,
                militar.nome,
                str(info.ordem) if info.ordem is not None else "—"
            ])

        table = Table(data, colWidths=[70, 70, 200, 60])
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
    except Exception as e:
        logger.error(f"Erro ao gerar PDF da escala {escala.pk}: {str(e)}")
        raise
