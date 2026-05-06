import os
import random
import numpy as np
from flask import Flask, render_template, request, url_for, session
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SelectField, FloatField, SubmitField, StringField
from wtforms.validators import DataRequired, NumberRange
from werkzeug.utils import secure_filename
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'секретныйключ2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['PROCESSED_FOLDER'] = 'static/processed'
app.config['HISTOGRAM_FOLDER'] = 'static/histograms'

for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER'], app.config['HISTOGRAM_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

Bootstrap(app)

class ImageForm(FlaskForm):
    image = FileField('Выберите изображение', validators=[FileRequired(), FileAllowed(['jpg','jpeg','png'], 'Только изображения!')])
    func_type = SelectField('Тип функции', choices=[('sin','Синус (sin)'),('cos','Косинус (cos)')], default='sin')
    direction = SelectField('Направление', choices=[('horizontal','Горизонтальное (по X)'),('vertical','Вертикальное (по Y)')], default='horizontal')
    period = FloatField('Период (в пикселях)', default=50, validators=[DataRequired(), NumberRange(min=10, max=500)])
    captcha_answer = StringField('Сколько будет:', validators=[DataRequired()])
    submit = SubmitField('Применить')

def apply_modulation(img_arr, func, direction, period):
    h, w, _ = img_arr.shape
    if direction == 'horizontal':
        x = np.arange(w)
        mod = np.sin(2 * np.pi * x / period) if func == 'sin' else np.cos(2 * np.pi * x / period)
        mod = (mod + 1) / 2
        mod = np.tile(mod, (h, 1))
    else:
        y = np.arange(h)
        mod = np.sin(2 * np.pi * y / period) if func == 'sin' else np.cos(2 * np.pi * y / period)
        mod = (mod + 1) / 2
        mod = np.tile(mod, (w, 1)).T
    mod = mod[:, :, np.newaxis]
    res = img_arr * mod
    return np.clip(res * 255, 0, 255).astype(np.uint8)

def plot_histograms(orig, mod, save_path):
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    colors = ('red', 'green', 'blue')
    titles = ('Красный канал', 'Зеленый канал', 'Синий канал')
    for i, (color, title) in enumerate(zip(colors, titles)):
        axes[0, i].hist(orig[:, :, i].ravel(), bins=50, color=color, alpha=0.7)
        axes[0, i].set_title(f'Исходное: {title}')
        axes[0, i].set_xlabel('Интенсивность')
        axes[0, i].set_ylabel('Частота')
        axes[1, i].hist(mod[:, :, i].ravel(), bins=50, color=color, alpha=0.7)
        axes[1, i].set_title(f'Модулированное: {title}')
        axes[1, i].set_xlabel('Интенсивность')
        axes[1, i].set_ylabel('Частота')
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    form = ImageForm()
    orig_url = mod_url = hist_url = None
    error = None
    
    # Генерация капчи при GET-запросе
    if request.method == 'GET':
        session['captcha_num1'] = random.randint(1, 10)
        session['captcha_num2'] = random.randint(1, 10)
    
    if form.validate_on_submit():
        # Проверка капчи
        expected = session.get('captcha_num1', 0) + session.get('captcha_num2', 0)
        try:
            user_answer = int(form.captcha_answer.data)
        except ValueError:
            user_answer = -1
        
        if user_answer != expected:
            error = "Неверный ответ капчи! Попробуйте ещё раз."
            session['captcha_num1'] = random.randint(1, 10)
            session['captcha_num2'] = random.randint(1, 10)
            return render_template('index.html', form=form, error=error,
                                 captcha_num1=session['captcha_num1'],
                                 captcha_num2=session['captcha_num2'])
        
        try:
            f = form.image.data
            filename = secure_filename(f.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            f.save(filepath)
            orig_url = url_for('static', filename=f'uploads/{filename}')
            img = np.array(Image.open(filepath).convert('RGB')) / 255.0
            mod_arr = apply_modulation(img, form.func_type.data, form.direction.data, form.period.data)
            mod_name = f"mod_{filename.split('.')[0]}.png"
            mod_path = os.path.join(app.config['PROCESSED_FOLDER'], mod_name)
            Image.fromarray(mod_arr).save(mod_path)
            mod_url = url_for('static', filename=f'processed/{mod_name}')
            hist_name = f"hist_{filename.split('.')[0]}.png"
            hist_path = os.path.join(app.config['HISTOGRAM_FOLDER'], hist_name)
            plot_histograms((img * 255).astype(np.uint8), mod_arr, hist_path)
            hist_url = url_for('static', filename=f'histograms/{hist_name}')
            
            # Генерируем новую капчу для следующего раза
            session['captcha_num1'] = random.randint(1, 10)
            session['captcha_num2'] = random.randint(1, 10)
            
        except Exception as e:
            error = str(e)
    
    # Получаем числа капчи из сессии
    captcha_num1 = session.get('captcha_num1', 5)
    captcha_num2 = session.get('captcha_num2', 3)
    
    return render_template('index.html', form=form, original_img=orig_url,
                          modulated_img=mod_url, histogram_img=hist_url,
                          error=error, captcha_num1=captcha_num1, captcha_num2=captcha_num2)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
