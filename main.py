"""Expense tracker (Kivy), lecture 6."""
import csv
import time
from datetime import datetime

import requests
from kivy.app import App
from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
from matplotlib.figure import Figure

# Firebase: https://<project>.firebaseio.com/expenses.json
CLOUD_URL = 'http://127.0.0.1:8000/expenses.json'

EXPENSE_CATEGORIES = ['Офис', 'Зарплаты', 'Маркетинг', 'Логистика', 'Налоги', 'Прочее']
INCOME_CATEGORIES = ['Продажи', 'Услуги', 'Прочее']

Builder.load_string('''
<ExpenseRow>:
    orientation: 'horizontal'
    padding: 10
    height: 60
    Label:
        text: root.category
        size_hint_x: 0.3
    Label:
        text: root.description
        size_hint_x: 0.4
    Label:
        text: ('+' if root.kind == 'Доход' else '-') + str(root.amount) + ' руб.'
        size_hint_x: 0.3
        color: (0, 0.6, 0, 1) if root.kind == 'Доход' else (1, 0, 0, 1)

<ExpensesRV>:
    viewclass: 'ExpenseRow'
    RecycleBoxLayout:
        default_size: None, dp(60)
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
        orientation: 'vertical'

<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        spacing: 10

        Label:
            text: 'БИЗНЕС-ТРЕКЕР РАСХОДОВ'
            font_size: 24
            bold: True
            color: 0.2, 0.4, 0.8, 1
            size_hint_y: 0.1

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.1
            Button:
                text: 'Добавить'
                on_press: root.show_add_popup()
            Button:
                text: 'Аналитика'
                on_press: root.show_analytics()
            Button:
                text: 'График'
                on_press: root.show_chart()

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.1
            Button:
                text: 'Экспорт'
                on_press: root.export_data()
            Button:
                text: 'Синхронизация'
                on_press: root.sync_cloud()

        Label:
            text: 'Доходы: ' + str(root.total_income) + ' руб.   Расходы: ' + str(root.total_expense) + ' руб.'
            size_hint_y: 0.07
        Label:
            text: 'Баланс: ' + str(root.balance) + ' руб.'
            font_size: 28
            bold: True
            color: (0, 0.6, 0, 1) if root.balance >= 0 else (1, 0, 0, 1)
            size_hint_y: 0.08

        ExpensesRV:
            id: rv
            size_hint_y: 0.55

<AddPopup>:
    size_hint: 0.8, 0.8
    title: 'Добавить запись'
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        spacing: 10

        Spinner:
            id: kind_spinner
            text: 'Расход'
            values: ['Расход', 'Доход']
            on_text: root.change_kind(self.text)
            size_hint_y: 0.15

        Spinner:
            id: category_spinner
            text: 'Выберите категорию'
            values: ['Офис', 'Зарплаты', 'Маркетинг', 'Логистика', 'Налоги', 'Прочее']
            size_hint_y: 0.15

        Label:
            text: 'Описание:'
        TextInput:
            id: description_input
            multiline: False
            size_hint_y: 0.15

        Label:
            text: 'Сумма (руб.):'
        TextInput:
            id: amount_input
            multiline: False
            input_filter: 'float'
            size_hint_y: 0.15

        BoxLayout:
            orientation: 'horizontal'
            spacing: 10
            size_hint_y: 0.2
            Button:
                text: 'Отмена'
                on_press: root.dismiss()
                background_color: 0.8, 0.2, 0.2, 1
            Button:
                text: 'Сохранить'
                on_press: root.save()
                background_color: 0.2, 0.6, 0.2, 1
''')


class ExpenseRow(RecycleDataViewBehavior, BoxLayout):
    category = StringProperty('')
    description = StringProperty('')
    amount = NumericProperty(0)
    kind = StringProperty('Расход')


class ExpensesRV(RecycleView):
    pass


class MainScreen(Screen):
    total_income = NumericProperty(0)
    total_expense = NumericProperty(0)
    balance = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = JsonStore('expenses.json')
        self.load_records()

    def load_records(self):
        rows = []
        income = 0
        expense = 0
        for key in sorted(self.store.keys(), reverse=True):
            record = self.store.get(key)
            kind = record.get('kind', 'Расход')
            rows.append({
                'category': record['category'],
                'description': record['description'],
                'amount': record['amount'],
                'kind': kind,
            })
            if kind == 'Доход':
                income += record['amount']
            else:
                expense += record['amount']
        self.ids.rv.data = rows
        self.total_income = income
        self.total_expense = expense
        self.balance = income - expense

    def show_add_popup(self):
        AddPopup(main_screen=self).open()

    def add_record(self, kind, category, description, amount):
        try:
            amount = float(amount)
        except ValueError:
            self.show_message('Ошибка', 'Введите корректную сумму')
            return
        key = 'record_' + str(int(time.time() * 1000))
        self.store.put(key, kind=kind, category=category, description=description,
                       amount=amount, date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self.load_records()

    def show_analytics(self):
        categories = {}
        for row in self.ids.rv.data:
            name = row['category'] + ' (' + row['kind'].lower() + ')'
            categories[name] = categories.get(name, 0) + row['amount']

        content = BoxLayout(orientation='vertical', padding=10)
        for name, total in categories.items():
            content.add_widget(Label(text=name + ': ' + str(total) + ' руб.', font_size=16))
        Popup(title='Аналитика по категориям', content=content, size_hint=(0.8, 0.6)).open()

    def show_chart(self):
        totals = {}
        for row in self.ids.rv.data:
            name = row['category'] + '\n' + row['kind'].lower()
            totals[name] = totals.get(name, 0) + row['amount']
        if not totals:
            self.show_message('График', 'Пока нет данных')
            return

        colors = ['green' if 'доход' in name else 'red' for name in totals]
        figure = Figure()
        axes = figure.add_subplot(111)
        axes.bar(list(totals.keys()), list(totals.values()), color=colors)
        axes.set_title('Доходы и расходы по категориям')
        axes.set_ylabel('руб.')
        axes.tick_params(axis='x', labelsize=8)

        Popup(title='График', content=FigureCanvasKivyAgg(figure), size_hint=(0.9, 0.8)).open()

    def export_data(self):
        try:
            with open('expenses_export.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Тип', 'Категория', 'Описание', 'Сумма', 'Дата'])
                for key in self.store.keys():
                    r = self.store.get(key)
                    writer.writerow([r.get('kind', 'Расход'), r['category'], r['description'],
                                     r['amount'], r.get('date', '')])
            self.show_message('Успех', 'Данные экспортированы в expenses_export.csv')
        except Exception as e:
            self.show_message('Ошибка', str(e))

    def sync_cloud(self):
        # download, add local records, upload back
        try:
            response = requests.get(CLOUD_URL, timeout=5)
            response.raise_for_status()
            records = response.json() or {}

            for key in self.store.keys():
                records[key] = self.store.get(key)

            requests.put(CLOUD_URL, json=records, timeout=5).raise_for_status()

            for key, record in records.items():
                self.store.put(key, **record)
            self.load_records()
            self.show_message('Успех', 'Синхронизация выполнена')
        except Exception:
            self.show_message('Ошибка', 'Нет связи с облаком')

    def show_message(self, title, message):
        Popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()


class AddPopup(Popup):
    """Add record window"""

    def __init__(self, main_screen, **kwargs):
        super().__init__(**kwargs)
        self.main_screen = main_screen

    def change_kind(self, kind):
        if kind == 'Доход':
            self.ids.category_spinner.values = INCOME_CATEGORIES
        else:
            self.ids.category_spinner.values = EXPENSE_CATEGORIES
        self.ids.category_spinner.text = 'Выберите категорию'

    def save(self):
        kind = self.ids.kind_spinner.text
        category = self.ids.category_spinner.text
        description = self.ids.description_input.text
        amount = self.ids.amount_input.text

        if category == 'Выберите категорию':
            self.main_screen.show_message('Ошибка', 'Выберите категорию')
            return
        if not description or not amount:
            self.main_screen.show_message('Ошибка', 'Заполните все поля')
            return

        self.main_screen.add_record(kind, category, description, amount)
        self.dismiss()


class ExpenseTrackerApp(App):
    def build(self):
        self.title = 'Business Expense Tracker'
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

    def on_pause(self):
        return True


if __name__ == '__main__':
    ExpenseTrackerApp().run()
