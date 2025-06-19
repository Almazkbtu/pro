from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, timedelta
from django.db.models import Sum, Count
from django.utils import timezone
import xlsxwriter
from io import BytesIO
import os

from .models import Payment, ParkingLog, ParkingSpot

class ReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30
        )

    def generate_receipt_pdf(self, payment):
        """Генерация PDF-чека об оплате"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        # Заголовок
        elements.append(Paragraph("Чек об оплате парковки", self.title_style))
        elements.append(Spacer(1, 20))

        # Информация о платеже
        data = [
            ["Номер чека:", str(payment.id)],
            ["Дата:", payment.payment_time.strftime("%d.%m.%Y %H:%M")],
            ["Номер автомобиля:", payment.parking_log.car.license_plate],
            ["Место парковки:", payment.parking_log.spot.number],
            ["Время въезда:", payment.parking_log.entry_time.strftime("%d.%m.%Y %H:%M")],
            ["Время выезда:", payment.parking_log.exit_time.strftime("%d.%m.%Y %H:%M") if payment.parking_log.exit_time else "Не выехал"],
            ["Сумма:", f"{payment.amount} руб."],
            ["Статус:", payment.get_status_display()]
        ]

        # Создаем таблицу
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.grey),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
        ]))

        elements.append(table)
        doc.build(elements)
        return buffer.getvalue()

    def generate_daily_report_excel(self, date=None):
        """Генерация отчета по загрузке парковки и выручке за день"""
        if date is None:
            date = timezone.now().date()

        # Получаем данные
        start_time = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        end_time = timezone.make_aware(datetime.combine(date, datetime.max.time()))

        # Статистика по местам
        spots_stats = ParkingSpot.objects.annotate(
            total_time=Sum('parkinglog__exit_time' - 'parkinglog__entry_time'),
            total_payments=Sum('parkinglog__payment__amount')
        ).filter(
            parkinglog__entry_time__gte=start_time,
            parkinglog__entry_time__lte=end_time
        )

        # Общая статистика
        total_payments = Payment.objects.filter(
            payment_time__gte=start_time,
            payment_time__lte=end_time,
            status='completed'
        ).aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id')
        )

        # Создаем Excel файл
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # Форматы
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1
        })
        cell_format = workbook.add_format({
            'border': 1
        })
        money_format = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00 ₽'
        })

        # Заголовок
        worksheet.merge_range('A1:E1', f'Отчет по парковке за {date.strftime("%d.%m.%Y")}', header_format)
        worksheet.write('A3', 'Общая статистика:', header_format)
        worksheet.write('B3', f'Выручка: {total_payments["total_amount"] or 0} ₽', money_format)
        worksheet.write('C3', f'Количество оплат: {total_payments["total_count"] or 0}', cell_format)

        # Заголовки таблицы
        headers = ['Место', 'Время использования (часы)', 'Выручка', 'Загрузка (%)']
        for col, header in enumerate(headers):
            worksheet.write(5, col, header, header_format)

        # Данные по местам
        row = 6
        for spot in spots_stats:
            total_hours = spot.total_time.total_seconds() / 3600 if spot.total_time else 0
            utilization = (total_hours / 24) * 100 if total_hours else 0

            worksheet.write(row, 0, spot.number, cell_format)
            worksheet.write(row, 1, total_hours, cell_format)
            worksheet.write(row, 2, spot.total_payments or 0, money_format)
            worksheet.write(row, 3, f'{utilization:.1f}%', cell_format)
            row += 1

        # График загрузки
        chart = workbook.add_chart({'type': 'column'})
        chart.add_series({
            'name': 'Загрузка парковки',
            'categories': f'=Sheet1!$A$6:$A${row-1}',
            'values': f'=Sheet1!$D$6:$D${row-1}',
        })
        worksheet.insert_chart('A20', chart)

        workbook.close()
        return output.getvalue()

    def generate_monthly_report_excel(self, year, month):
        """Генерация месячного отчета"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        # Получаем данные по дням
        daily_stats = []
        current_date = start_date
        while current_date < end_date:
            next_date = current_date + timedelta(days=1)
            stats = Payment.objects.filter(
                payment_time__gte=current_date,
                payment_time__lt=next_date,
                status='completed'
            ).aggregate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            )
            daily_stats.append({
                'date': current_date,
                'amount': stats['total_amount'] or 0,
                'count': stats['total_count'] or 0
            })
            current_date = next_date

        # Создаем Excel файл
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # Форматы
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1
        })
        cell_format = workbook.add_format({
            'border': 1
        })
        money_format = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00 ₽'
        })
        date_format = workbook.add_format({
            'border': 1,
            'num_format': 'dd.mm.yyyy'
        })

        # Заголовок
        worksheet.merge_range('A1:C1', f'Месячный отчет за {start_date.strftime("%B %Y")}', header_format)

        # Заголовки таблицы
        headers = ['Дата', 'Выручка', 'Количество оплат']
        for col, header in enumerate(headers):
            worksheet.write(2, col, header, header_format)

        # Данные по дням
        row = 3
        total_amount = 0
        total_count = 0
        for stat in daily_stats:
            worksheet.write(row, 0, stat['date'], date_format)
            worksheet.write(row, 1, stat['amount'], money_format)
            worksheet.write(row, 2, stat['count'], cell_format)
            total_amount += stat['amount']
            total_count += stat['count']
            row += 1

        # Итоги
        worksheet.write(row + 1, 0, 'ИТОГО:', header_format)
        worksheet.write(row + 1, 1, total_amount, money_format)
        worksheet.write(row + 1, 2, total_count, cell_format)

        # График выручки
        chart = workbook.add_chart({'type': 'line'})
        chart.add_series({
            'name': 'Выручка',
            'categories': f'=Sheet1!$A$3:$A${row}',
            'values': f'=Sheet1!$B$3:$B${row}',
        })
        worksheet.insert_chart('A20', chart)

        workbook.close()
        return output.getvalue() 