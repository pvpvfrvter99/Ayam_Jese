from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from collections import Counter
from sqlalchemy import func
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os
import requests
from flask import flask, request, flash, redirect, url_for
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ayamjeze2026-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restoran.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
db = SQLAlchemy(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# MODEL DATABASE
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Menu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    harga = db.Column(db.Integer, nullable=False)
    foto = db.Column(db.String(200), default='default.jpg')
    deskripsi = db.Column(db.String(200), default='')

class Pesanan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nomor_meja = db.Column(db.Integer, nullable=False)
    nama = db.Column(db.String(100))
    menu = db.Column(db.String(100))
    total = db.Column(db.Integer)
    tanggal = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default="Menunggu")
    status_bayar = db.Column(db.String(20), default="Belum Bayar")
    metode_bayar = db.Column(db.String(20), default="Cash")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ROUTE CUSTOMER - PILIH MEJA DULU
@app.route('/')
def index():
    return render_template('pilih_meja.html')

@app.route('/meja/<int:nomor>')
def meja(nomor):
    menus = Menu.query.all()
    return render_template('order.html', nomor_meja=nomor, menus=menus)

@app.route('/pesan', methods=['POST'])
def pesan():
    nomor_meja = int(request.form['nomor_meja'])
    nama = request.form['nama']
    metode_bayar = request.form['metode_bayar']

    # Ambil semua menu yang dikirim dari form
    menu_ids = request.form.getlist('menu_id[]')
    jumlahs = request.form.getlist('jumlah[]')

    for i in range(len(menu_ids)):
        menu_id = int(menu_ids[i])
        jumlah = int(jumlahs[i])

        if jumlah > 0: # cuma simpan kalau jumlah > 0
            menu_obj = Menu.query.get(menu_id)
            total = menu_obj.harga * jumlah

            pesanan_baru = Pesanan(
                nomor_meja=nomor_meja,
                nama=nama,
                menu=f"{menu_obj.nama} x{jumlah}", # simpan "Ayam Crispy x3"
                total=total,
                metode_bayar=metode_bayar
            )
            db.session.add(pesanan_baru)

    db.session.commit()
    flash(f'Pesanan Meja {nomor_meja} berhasil dikirim!', 'success')
    return redirect(f'/meja/{nomor_meja}')
# ROUTE KASIR
@app.route('/kasir')
@login_required
def kasir():
    pesanan = Pesanan.query.filter_by(status_bayar="Belum Bayar").all()
    return render_template('kasir.html', pesanan=pesanan)

@app.route('/meja_detail/<int:nomor>')
def meja_detail(nomor):
    pesanan = Pesanan.query.filter_by(nomor_meja=nomor, status_bayar="Belum Bayar").all()
    total_meja = sum(p.total for p in pesanan)
    return render_template('meja_detail.html', pesanan=pesanan, nomor_meja=nomor, total_meja=total_meja)

@app.route('/bayar_meja/<int:nomor>')
def bayar_meja(nomor):
    Pesanan.query.filter_by(nomor_meja=nomor, status_bayar="Belum Bayar").update({
        'status_bayar': 'Lunas',
        'status': 'Selesai'
    })
    db.session.commit()
    flash(f'Meja {nomor} berhasil dibayar!', 'success')
    return redirect('/kasir')

# ROUTE LAPORAN
@app.route('/laporan')
@login_required
def laporan():
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    query = Pesanan.query.filter_by(status="Selesai")

    if start_date and end_date:
        query = query.filter(Pesanan.tanggal.between(start_date, end_date))
    else:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        query = query.filter(Pesanan.tanggal >= start_date)

    pesanan_selesai = query.all()
    total_omset = sum(p.total for p in pesanan_selesai)
    total_transaksi = len(pesanan_selesai)
    menu_list = [p.menu for p in pesanan_selesai]
    menu_terlaris = Counter(menu_list).most_common(5)

    omset_harian = db.session.query(
        func.strftime('%d-%m', Pesanan.tanggal),
        func.sum(Pesanan.total)
    ).filter_by(status="Selesai").filter(
        Pesanan.tanggal.between(start_date, end_date)
    ).group_by(func.strftime('%d-%m', Pesanan.tanggal)).order_by(func.date(Pesanan.tanggal)).all()

    return render_template('laporan.html',
                         pesanan=pesanan_selesai,
                         total_omset=total_omset,
                         total_transaksi=total_transaksi,
                         menu_terlaris=menu_terlaris,
                         omset_harian=omset_harian,
                         start_date=start_date,
                         end_date=end_date)

@app.route('/export_excel')
@login_required
def export_excel():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    query = Pesanan.query.filter_by(status="Selesai")
    if start_date and end_date:
        query = query.filter(Pesanan.tanggal.between(start_date, end_date))

    pesanan = query.all()
    total_omset = sum(p.total for p in pesanan)

    # Data utama
    data = [{
        'Tanggal': p.tanggal.strftime('%d-%m-%Y %H:%M'),
        'Meja': p.nomor_meja,
        'Nama Pemesan': p.nama,
        'Menu': p.menu,
        'Total': p.total,
        'Metode Bayar': p.metode_bayar
    } for p in pesanan]

    df = pd.DataFrame(data)
    
    # Buat Excel di memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Laporan', index=False, startrow=2)
        worksheet = writer.sheets['Laporan']
        
        # Header resto
        worksheet['A1'] = 'LAPORAN PENJUALAN - RESTORAN AYAM JEZE'
        worksheet['A2'] = f'Periode: {start_date} s/d {end_date} | Total Omset: Rp {total_omset:,}'
        
        # Atur lebar kolom biar rapi
        worksheet.column_dimensions['A'].width = 18  # Tanggal
        worksheet.column_dimensions['B'].width = 8   # Meja
        worksheet.column_dimensions['C'].width = 20  # Nama
        worksheet.column_dimensions['D'].width = 30  # Menu
        worksheet.column_dimensions['E'].width = 15  # Total
        worksheet.column_dimensions['F'].width = 15  # Metode

    output.seek(0)
    filename = f'laporan_ayamjeze_{start_date}_s_d_{end_date}.xlsx'
    return send_file(output, download_name=filename, as_attachment=True)
@app.route('/export_pdf')
@login_required
def export_pdf():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    query = Pesanan.query.filter_by(status="Selesai")
    if start_date and end_date:
        query = query.filter(Pesanan.tanggal.between(start_date, end_date))

    pesanan = query.all()
    total_omset = sum(p.total for p in pesanan)

    # Buat PDF di memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Judul
    title = Paragraph("Laporan Penjualan - Restoran Ayam Jeze", styles['Title'])
    elements.append(title)
    
    # Info tanggal
    subtitle = Paragraph(f"Periode: {start_date} s/d {end_date}", styles['Normal'])
    elements.append(subtitle)
    elements.append(Paragraph(f"Total Omset: Rp {total_omset:,}", styles['Heading2']))
    elements.append(Paragraph("<br/>", styles['Normal']))

    # Data tabel
    data = [['Tanggal', 'Meja', 'Nama', 'Menu', 'Total', 'Metode']]
    for p in pesanan:
        data.append([
            p.tanggal.strftime('%d-%m-%Y %H:%M'),
            f"Meja {p.nomor_meja}",
            p.nama,
            p.menu,
            f"Rp {p.total:,}",
            p.metode_bayar
        ])

    # Style tabel
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B0000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#2a0000')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#FFD700'))
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    
    return send_file(buffer, download_name=f'laporan_{start_date}_s_d_{end_date}.pdf', as_attachment=True)

# ROUTE LOGIN ADMIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect('/admin')
        flash('Username atau password salah!', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# ROUTE ADMIN DASHBOARD
@app.route('/admin')
@login_required
def admin():
    menus = Menu.query.all()
    pesanan_baru = Pesanan.query.filter_by(status="Menunggu").order_by(Pesanan.tanggal.desc()).limit(10).all()
    total_pesanan = Pesanan.query.count()
    total_menu = Menu.query.count()
    return render_template('admin.html', menus=menus, pesanan_baru=pesanan_baru,
                         total_pesanan=total_pesanan, total_menu=total_menu)

@app.route('/admin/menu/tambah', methods=['POST'])
@login_required
def tambah_menu():
    nama = request.form['nama']
    harga = int(request.form['harga'])
    deskripsi = request.form['deskripsi']
    foto = request.files['foto']

    filename = 'default.jpg'
    if foto and allowed_file(foto.filename):
        filename = secure_filename(foto.filename)
        foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    menu_baru = Menu(nama=nama, harga=harga, deskripsi=deskripsi, foto=filename)
    db.session.add(menu_baru)
    db.session.commit()
    flash('Menu berhasil ditambahkan!', 'success')
    return redirect('/admin')

@app.route('/admin/menu/hapus/<int:id>')
@login_required
def hapus_menu(id):
    menu = Menu.query.get(id)
    db.session.delete(menu)
    db.session.commit()
    flash('Menu berhasil dihapus!', 'success')
    return redirect('/admin')

@app.route('/admin/pesanan/selesai/<int:id>')
@login_required
def selesai_pesanan(id):
    pesanan = Pesanan.query.get(id)
    pesanan.status = 'Selesai'
    db.session.commit()
    return redirect('/admin')
def kirim_wa_admin(pesanan):
    """Kirim notifikasi WA ke admin pas ada pesanan baru"""
    token = "GANTI_DENGAN_TOKEN_FONNTE_KAMU"  # Daftar di fonnte.com gratis 20 chat/hari
    nomor_admin = "62812xxxxxx"  # Ganti: 62 + nomor kamu tanpa 0. Contoh: 628123456789
    
    pesan = f"""🍗 *PESAN BARU - AYAM JEZE* 🍗

*Meja:* {pesanan.nomor_meja}
*Nama:* {pesanan.nama}
*Menu:* {pesanan.menu}
*Total:* Rp {pesanan.total:,}
*Metode:* {pesanan.metode_bayar}
*Waktu:* {pesanan.tanggal.strftime('%d/%m/%Y %H:%M:%S')}

Status: ⏳ *MENUNGGU KONFIRMASI*
Silakan cek dashboard admin!"""

    url = "https://api.fonnte.com/send"
    data = {
        "target": nomor_admin,
        "message": pesan,
        "countryCode": "62"
    }
    headers = {
        "Authorization": token
    }
    try:
        requests.post(url, data=data, headers=headers, timeout=5)
    except:
        print("Gagal kirim WA, cek token/nomor")

# JALANKAN APP
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Buat admin default: username=admin password=admin123
        if User.query.count() == 0:
            admin = User(username='admin', password=generate_password_hash('admin123'))
            db.session.add(admin)
        # Menu default
        if Menu.query.count() == 0:
            default_menus = [
                Menu(nama="Ayam Crispy", harga=15000, deskripsi="Ayam crispy renyah", foto="default.jpg"),
                Menu(nama="Ayam Geprek", harga=17000, deskripsi="Pedas nampol", foto="default.jpg"),
                Menu(nama="Nasi + Ayam", harga=18000, deskripsi="Paket lengkap", foto="default.jpg"),
                Menu(nama="Es Teh", harga=5000, deskripsi="Segar manis", foto="default.jpg"),
                Menu(nama="Es Jeruk", harga=6000, deskripsi="Asem segar", foto="default.jpg")
            ]
            db.session.add_all(default_menus)
        db.session.commit()
@app.route('/kirim_pesanan/<int:nomor_meja>', methods=['POST'])
def kirim_pesanan(nomor_meja):
    nama = request.form['nama']
    menu = request.form['menu']
    total = int(request.form['total'])
    metode_bayar = request.form['metode_bayar']

    pesanan_baru = Pesanan(
        nomor_meja=nomor_meja,
        nama=nama,
        menu=menu,
        total=total,
        metode_bayar=metode_bayar
    )
    db.session.add(pesanan_baru)
    db.session.commit()
    
    kirim_wa_admin(pesanan_baru)  # <-- TAMBAH INI DOANG

@app.route('/order', methods=['POST'])
def order():
    # ... kode simpan pesanan kamu ...
    flash('Pesanan Berhasil!', 'success')
    return redirect(url_for('order'))
    
    return render_template('sukses.html', pesanan=pesanan_baru)
if __name__ == "__main__":
                import os
                port = int(os.environ.get("PORT", 5000))
                app.run(host="0.0.0.0", port=port)
app = Flask(__name__)  # <-- WAJIB namanya "app"
app.secret_key = os.environ.get('SECRET_KEY', 'ayam-jeze-fallback')
