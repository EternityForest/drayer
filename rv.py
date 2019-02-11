#Entire file is https://stackoverflow.com/questions/48287204/recycleview-module-in-kivy but modded

from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.label import Label
from kivy.properties import BooleanProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior

class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    ''' Adds selection and focus behaviour to the view. '''
    def __init__(self, touch_multiselect=False, **kw):
        super().__init__(**kw, default_size=(0, 28), default_size_hint=(1, None), size_hint_y=None,
                          multiselect=True, orientation='vertical')

        self.bind(minimum_height=self._min)

    def _min(self, inst, val):
        self.height = val

class SelectableLabel(RecycleDataViewBehavior, Label):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def __init__(self,value=None, **kw):
        super().__init__(**kw)
        self.value=value

        self.canvas.before.clear()
        with self.canvas.before:
            if self.selected:
                Color(.0, 0.9, .1, .3)
            else:
                Color(0, 0, 0, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, inst, value):
        self.rect.pos = inst.pos
        self.rect.size = inst.size

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super().refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(SelectableLabel, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            self.parent.parent.selected = self.value
            self.parent.parent.onSelect(self.value)
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        self.canvas.before.clear()
        with self.canvas.before:
            if self.selected:
                Color(.0, 0.9, .1, .3)
            else:
                Color(0, 0, 0, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)


class RV(RecycleView):
    def __init__(self, **kwargs):
        super(RV, self).__init__(**kwargs)
        self.add_widget(SelectableRecycleBoxLayout())
        self.viewclass = 'SelectableLabel'
        self.data = [{'text': str(x)} for x in range(100)]
        self.selected=None
        self.onSelect= lambda x:0
