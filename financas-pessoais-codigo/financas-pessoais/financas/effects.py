"""Efeitos vetoriais nativos do Qt, sem navegador, imagens remotas ou rede."""
import math
from PySide6.QtCore import Qt,QRectF,QPointF,QSize,QVariantAnimation,QEasingCurve,QTimer,Signal
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QLinearGradient,QRadialGradient,QFont
from PySide6.QtWidgets import QPushButton,QAbstractButton,QListWidget,QStyledItemDelegate,QStyle,QWidget,QSizePolicy
from .appearance import colors
from .typography import FONT_FAMILY


def mix(a,b,progress):
    a,b=QColor(a),QColor(b);p=max(0,min(1,progress))
    return QColor(round(a.red()+(b.red()-a.red())*p),round(a.green()+(b.green()-a.green())*p),
                  round(a.blue()+(b.blue()-a.blue())*p),round(a.alpha()+(b.alpha()-a.alpha())*p))


class SaveButton(QPushButton):
    """Pílula em grafite e cinza fosco com cápsula expansível e pressão de 95%."""
    def __init__(self,text='',parent=None):
        super().__init__(text,parent)
        self.progress=0.;self.press_scale=1.
        self.hover_animation=QVariantAnimation(self);self.hover_animation.setDuration(300)
        self.hover_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.hover_animation.valueChanged.connect(self._hover_value)
        self.press_animation=QVariantAnimation(self);self.press_animation.setDuration(100)
        self.press_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.press_animation.valueChanged.connect(self._press_value)
        self.pressed.connect(lambda:self._press_to(.95));self.released.connect(lambda:self._press_to(1.))
        self.setCursor(Qt.PointingHandCursor);self.setMinimumHeight(42)
        self.setToolTip(text);self.setAccessibleName(text)
        self.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(max(112,self.fontMetrics().horizontalAdvance(self.text())+65),44)

    def minimumSizeHint(self):return self.sizeHint()
    def _hover_value(self,value):self.progress=float(value);self.update()
    def _press_value(self,value):self.press_scale=float(value);self.update()
    def _press_to(self,target):
        self.press_animation.stop();self.press_animation.setStartValue(self.press_scale)
        self.press_animation.setEndValue(target);self.press_animation.start()
    def animate_hover(self,hover):
        self.hover_animation.stop();self.hover_animation.setStartValue(self.progress)
        self.hover_animation.setEndValue(1. if hover else 0.);self.hover_animation.start()
    def enterEvent(self,event):self.animate_hover(True);super().enterEvent(event)
    def leaveEvent(self,event):self.animate_hover(False);super().leaveEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():p.setOpacity(.45)
        p.translate(self.width()/2,self.height()/2);p.scale(self.press_scale,self.press_scale)
        p.translate(-self.width()/2,-self.height()/2)
        rect=QRectF(2,2,self.width()-4,self.height()-4);c=colors()
        p.setPen(QPen(QColor(c['border']),1));p.setBrush(QColor(c['save_bg']));p.drawRoundedRect(rect,21,21)
        capsule=QRectF(8,8,30+(self.width()-46)*self.progress,self.height()-16)
        gradient=QLinearGradient(capsule.topLeft(),capsule.bottomLeft())
        gradient.setColorAt(0,QColor(c['save_top']));gradient.setColorAt(1,QColor(c['save_bottom']))
        p.setPen(Qt.NoPen);p.setBrush(gradient);p.drawRoundedRect(capsule,16,16)
        # O ícone continua em posição estável enquanto a cápsula cobre o texto.
        x=23.;y=self.height()/2
        icon=QPainterPath();icon.moveTo(x-4,y-7);icon.lineTo(x+4,y-7);icon.lineTo(x+4,y+7)
        icon.lineTo(x,y+3);icon.lineTo(x-4,y+7);icon.closeSubpath()
        p.setPen(QPen(QColor(c['save_icon']),1.5));p.setBrush(QColor(c['save_icon']));p.drawPath(icon)
        p.save();p.setOpacity((1-self.progress)*(1. if self.isEnabled() else .45))
        p.setPen(QColor(c['save_text']));font=QFont(self.font());font.setWeight(QFont.DemiBold);p.setFont(font)
        p.drawText(QRectF(44+10*self.progress,0,self.width()-54,self.height()),Qt.AlignVCenter|Qt.AlignLeft,self.text());p.restore()
        if self.hasFocus():
            p.setPen(QPen(QColor(colors()['accent']),2));p.setBrush(Qt.NoBrush);p.drawRoundedRect(rect,21,21)
        p.end()


class MenuDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(210,50)
    def paint(self,p,option,index):
        c=colors();row=index.row();nav=self.parent();t=nav.hover_progress.get(row,0.)
        selected=bool(option.state & QStyle.State_Selected)
        p.save();p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(option.rect).adjusted(4,3,-4,-3);path=QPainterPath();path.addRoundedRect(rect,22,22)
        if t>0:
            for extra in range(5,0,-1):
                glow=QColor(c['text']);glow.setAlpha(round(3*t))
                p.setPen(QPen(glow,extra*2));p.setBrush(Qt.NoBrush);p.drawRoundedRect(rect,22,22)
        p.setPen(QPen(QColor(c['border']),1));p.setBrush(QColor(c['selected'] if selected else c['sidebar']))
        p.drawRoundedRect(rect,22,22)
        p.save();p.setClipPath(path)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#333333'))
        radius=math.hypot(rect.width(),rect.height())*t
        p.drawEllipse(rect.topLeft(),radius,radius);p.restore()
        p.setPen(mix(c['text'] if selected else c['muted'],'#ffffff',t))
        font=QFont(option.font);font.setWeight(QFont.DemiBold)
        font.setLetterSpacing(QFont.PercentageSpacing,102);p.setFont(font)
        p.drawText(rect.adjusted(14,0,-10,0),Qt.AlignVCenter|Qt.AlignLeft,index.data())
        if option.state & QStyle.State_HasFocus:
            p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(c['accent']),1.5));p.drawRoundedRect(rect,22,22)
        p.restore()


class AnimatedMenu(QListWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.hover_progress={};self.animations={};self.hovered=-1
        self.setMouseTracking(True);self.viewport().setMouseTracking(True)
        self.setItemDelegate(MenuDelegate(self));self.setSpacing(3)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName('Menu principal da BatFinanças')
    def animate_row(self,row,target):
        if row<0:return
        animation=self.animations.get(row)
        if animation is None:
            animation=QVariantAnimation(self);animation.setDuration(500)
            animation.setEasingCurve(QEasingCurve.InOutCubic)
            animation.valueChanged.connect(lambda value,r=row:self._value(r,value));self.animations[row]=animation
        animation.stop();animation.setStartValue(self.hover_progress.get(row,0.))
        animation.setEndValue(target);animation.start()
    def _value(self,row,value):self.hover_progress[row]=float(value);self.viewport().update()
    def mouseMoveEvent(self,event):
        row=self.indexAt(event.position().toPoint()).row()
        if row!=self.hovered:
            self.animate_row(self.hovered,0.);self.hovered=row;self.animate_row(row,1.)
        super().mouseMoveEvent(event)
    def leaveEvent(self,event):
        self.animate_row(self.hovered,0.);self.hovered=-1;super().leaveEvent(event)
    def mousePressEvent(self,event):
        row=self.indexAt(event.position().toPoint()).row()
        if row!=self.hovered:self.animate_row(self.hovered,0.)
        self.hovered=row;self.animate_row(row,1.);super().mousePressEvent(event)


class ThemeToggle(QAbstractButton):
    """Botão circular com relevo, pressão e transição sol/lua de 300 ms."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setCheckable(True);self.setFixedSize(44,44);self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus);self.progress=0.
        self.animation=QVariantAnimation(self);self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutCubic);self.animation.valueChanged.connect(self._value)
        self.toggled.connect(self._changed);self.set_dark(True,animate=False)
    def _value(self,value):self.progress=float(value);self.update()
    def _changed(self,dark):
        self.animation.stop();self.animation.setStartValue(self.progress);self.animation.setEndValue(1. if dark else 0.)
        self.animation.start();self._labels()
    def _labels(self):
        text='Alternar para modo claro' if self.isChecked() else 'Alternar para modo escuro'
        self.setAccessibleName(text);self.setToolTip(text)
    def set_dark(self,dark,animate=True,notify=True):
        previous=self.blockSignals(not notify or not animate)
        self.setChecked(dark);self.blockSignals(previous)
        if not animate:
            self.animation.stop();self.progress=float(bool(dark));self._labels();self.update()
        elif not notify:
            self._changed(dark)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.scale(self.width()/72.,self.height()/72.)
        rect=QRectF(9,7,54,54);pressed=self.isDown();t=self.progress
        if pressed:rect.translate(0,2)
        shadow=QRadialGradient(QPointF(36,42),34)
        shadow.setColorAt(0,QColor(0,0,0,90));shadow.setColorAt(.65,QColor(0,0,0,60));shadow.setColorAt(1,QColor(0,0,0,0))
        p.setPen(Qt.NoPen);p.setBrush(shadow);p.drawEllipse(QRectF(2,6,68,66))
        gradient=QLinearGradient(rect.topLeft(),rect.bottomLeft())
        gradient.setColorAt(0,mix('#ffffff','#444955',t));gradient.setColorAt(1,mix('#ceced1','#21242d',t))
        p.setBrush(gradient);p.setPen(QPen(mix('#ffffff','#646b79',t),1));p.drawEllipse(rect)
        inner=rect.adjusted(3,3,-3,-3)
        bevel=QLinearGradient(inner.topLeft(),inner.bottomLeft())
        bevel.setColorAt(0,QColor(0,0,0,70 if pressed or self.isChecked() else 12))
        bevel.setColorAt(.4,QColor(0,0,0,0));bevel.setColorAt(1,QColor(255,255,255,90))
        p.setBrush(Qt.NoBrush);p.setPen(QPen(bevel,3));p.drawEllipse(inner)
        center=rect.center();size=.92 if pressed else 1.
        p.save();p.translate(center);p.scale(size,size);p.rotate(35*t)
        p.setOpacity(1-t);p.setPen(QPen(QColor('#555b60'),2));p.setBrush(QColor('#9ba1a6'))
        p.drawEllipse(QPointF(0,0),7,7)
        for i in range(8):
            angle=math.pi*i/4;p.drawLine(QPointF(math.cos(angle)*11,math.sin(angle)*11),QPointF(math.cos(angle)*15,math.sin(angle)*15))
        p.setOpacity(t)
        moon=QPainterPath();moon.addEllipse(QPointF(0,0),13,13)
        cut=QPainterPath();cut.addEllipse(QPointF(6,-5),12,12)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#c5c9cd'));p.drawPath(moon.subtracted(cut));p.restore()
        if self.hasFocus():
            p.setPen(QPen(QColor(colors()['accent']),2));p.setBrush(Qt.NoBrush);p.drawEllipse(rect.adjusted(-3,-3,3,3))
        p.end()


def bat_path():
    """Silhueta simétrica com asas recortadas, orelhas e cauda, em vetor."""
    p=QPainterPath();p.moveTo(0,.47)
    p.cubicTo(-.08,.16,-.22,.08,-.36,.04)
    p.cubicTo(-.49,0,-.61,-.01,-.70,.02)
    p.cubicTo(-.62,-.22,-.73,-.38,-1.,-.50)
    p.lineTo(-.33,-.50)
    p.cubicTo(-.29,-.49,-.33,-.25,-.18,-.24)
    p.cubicTo(-.14,-.23,-.09,-.27,-.08,-.52)
    p.lineTo(-.032,-.34);p.quadTo(0,-.36,.032,-.34);p.lineTo(.08,-.52)
    p.cubicTo(.09,-.27,.14,-.23,.18,-.24)
    p.cubicTo(.33,-.25,.29,-.49,.33,-.50)
    p.lineTo(1.,-.50)
    p.cubicTo(.73,-.38,.62,-.22,.70,.02)
    p.cubicTo(.61,-.01,.49,0,.36,.04)
    p.cubicTo(.22,.08,.08,.16,0,.47);p.closeSubpath()
    return p


class BatIntro(QWidget):
    """Abertura por execução: asas se expandem e revelam a janela pronta."""
    finished=Signal()
    def __init__(self,parent):
        super().__init__(parent)
        self.progress=0.;self._finished=False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus);self.setAccessibleName('Abertura da BatFinanças; pressione Esc para continuar')
        self.animation=QVariantAnimation(self);self.animation.setDuration(1650)
        self.animation.setStartValue(0.);self.animation.setEndValue(1.)
        self.animation.valueChanged.connect(self._value);self.animation.finished.connect(self.finish)
        self.setGeometry(parent.rect())
    def _value(self,value):self.progress=float(value);self.update()
    def start(self):
        self.setGeometry(self.parentWidget().rect());self.show();self.raise_();self.setFocus();self.animation.start()
    def finish(self):
        if self._finished:return
        self._finished=True;self.animation.stop();self.hide();self.finished.emit();self.deleteLater()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Escape,Qt.Key_Return,Qt.Key_Space):self.finish()
        else:super().keyPressEvent(event)
    def mousePressEvent(self,event):self.finish()
    def paintEvent(self,event):
        t=self.progress;fade=max(0.,1-max(0.,t-.74)/.26)
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setOpacity(fade)
        p.fillRect(self.rect(),QColor('#090a0d'))
        center=QPointF(self.width()/2,self.height()*.43)
        glow=QRadialGradient(center,min(self.width(),self.height())*.55)
        glow.setColorAt(0,QColor(150,155,160,40));glow.setColorAt(1,QColor(10,10,13,0))
        p.setPen(Qt.NoPen);p.setBrush(glow);p.drawRect(self.rect())
        opening=QEasingCurve(QEasingCurve.OutCubic).valueForProgress(min(1.,t/.72))
        spread=.07+.93*opening;zoom=1+max(0.,t-.76)*3
        scale=min(self.width()*.42,self.height()*.56)*zoom
        p.save();p.translate(center);p.scale(scale*spread,scale)
        p.setPen(QPen(QColor('#969b9f'),.003));p.setBrush(QColor('#26282b'));p.drawPath(bat_path());p.restore()
        p.setOpacity(fade*min(1,t*4));p.setPen(QColor('#d0d3d5'))
        font=QFont(FONT_FAMILY,24,QFont.DemiBold);p.setFont(font)
        p.drawText(QRectF(10,self.height()*.70,self.width()-20,58),Qt.AlignCenter,'BatFinanças')
        p.setFont(QFont(FONT_FAMILY,9));p.setPen(QColor('#aeb2bc'))
        p.drawText(QRectF(10,self.height()*.70+60,self.width()-20,35),Qt.AlignCenter,'Seu controle financeiro pessoal')
        p.setOpacity(fade);p.setFont(QFont(FONT_FAMILY,8))
        p.drawText(QRectF(10,self.height()-55,self.width()-20,30),Qt.AlignCenter,'Clique ou pressione Esc para continuar')
        p.end()
