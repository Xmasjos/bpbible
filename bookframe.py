import wx
from displayframe import AUIDisplayFrame
from displayframe import IN_BOTH, IN_MENU
from tooltip import BiblicalPermanentTooltip
import versetree
import urllib


from swlib.pysw import VK, VerseParsingError
from swlib.pysw import GetVerseStr, GetBestRange

from swlib import pysw
from util.unicode import to_str, to_unicode
from gui import guiutil
import config
import guiconfig
from moduleinfo import ModuleInfo
from gui.menu import MenuItem, Separator
from dictionarylist import DictionarySelector
from gui.quickselector import QuickSelector

import events
from util.i18n import N_


class BookFrame(AUIDisplayFrame):
	has_menu = True
	shows_info = True
	use_quickselector = True
	def __init__(self, parent):
		super(BookFrame, self).__init__(parent)
		self.reference = ""
		self.last_version_used = ""
		self.setup()

	def notify(self, ref, source=None, settings_changed=False):
		self.SetReference(ref, settings_changed=settings_changed)

	def SetBook(self, book):
		self.book = book

	def SetPage(self, page_content):
		# close all open tooltips
		guiconfig.mainfrm.hide_tooltips()
		return super(BookFrame, self).SetPage(page_content)

	def get_verified_one_verse(self, ref):
		try:
			ref = GetVerseStr(ref, self.reference, 
				raiseError=True, userInput=True, userOutput=False)
			return ref
		
		except VerseParsingError, e:
			wx.MessageBox(str(e), config.name())
		
	def get_verified_multi_verses(self, ref):
		try:
			ref = GetBestRange(ref, self.reference, 
				raiseError=True, userInput=True, userOutput=False)
			return ref
		
		except VerseParsingError, e:
			wx.MessageBox(str(e), config.name())	
		


	@guiutil.frozen
	def SetReference(self, ref, settings_changed=False):
		self.reference = ref
		self.ChangeReference(self.reference, settings_changed)

	def ChangeReference(self, reference, settings_changed=False):
		settings_changed = settings_changed or (self.last_version_used != self.book.version)
		self.last_version_used = self.book.version
		has_selected_new_segment = False
		if self.dom_loaded:
			# If the settings have changed we want to do a complete reload anyway
			# (since it could be something that requires a complete reload, such as changing version).
			if not settings_changed:
				has_selected_new_segment = self.ExecuteScriptWithResult('select_new_segment("%s")' % self.get_ref_id(reference))
				has_selected_new_segment = (has_selected_new_segment == "true")

		if not has_selected_new_segment:
			self.OpenURIForCurrentBook("bpbible://content/page/%s/%s" % (self.book.version, reference))
		self.update_title()

	def get_ref_id(self, reference):
		return urllib.quote(reference.encode("utf8"))

	def OpenURIForCurrentBook(self, url):
		if self.book.mod is not None:
			self.OpenURI(url)
		else:
			self.SetPage(config.MODULE_MISSING_STRING())
		
	@property
	def SetReference_from_string(self):
		# by default use SetReference
		return self.SetReference

	def setup(self):
		self.book = None
		
		super(BookFrame, self).setup()
		self.add_custom_dom_event_listener('ChangeSegment', self.handle_current_segment_changed_event)

	def get_actions(self):
		actions = super(BookFrame, self).get_actions()
		actions.update({
			# Navigation shortcuts.
			wx.WXK_F5: self.chapter_back,
			wx.WXK_F8: self.chapter_forward,
			(wx.WXK_LEFT, wx.MOD_CMD): self.chapter_back,
			(wx.WXK_RIGHT, wx.MOD_CMD): self.chapter_forward,
			# Emulation of vi, Gmail, Google Reader, etc.
			ord("K"): self.chapter_back,
			ord("J"): self.chapter_forward,

			# Search shortcuts.
			ord("S"): self.search_quickly,
			ord("P"): (lambda: self.search_results_move(-1)),
			ord("N"): (lambda: self.search_results_move(1)),
			# More Vi emulation.  Shift-N = previous search result.
			(ord("N"), wx.MOD_SHIFT): (lambda: self.search_results_move(-1)),
			(ord("G"), wx.MOD_CMD): self.focus_reference_textbox,
		})

		if self.use_quickselector:
			actions[ord("G")] = self.go_quickly
		
		return actions

	def search_results_move(self, amount):
		search_panel = self.get_search_panel_for_frame()
		assert search_panel, "Search panel not found for %s" % self
		search_panel.next_search_result(amount)
			
			
	def chapter_move(self, amount): pass

	def chapter_forward(self):
		"""Move to next article"""
		self.chapter_move(1)
	
	def chapter_back(self):
		"""Move to previous article"""
		self.chapter_move(-1)
	
	def reload(self, event=None, settings_changed=False):
		if event and not event.settings_changed:
			return

		settings_changed = settings_changed or (event and event.settings_changed)
		self.SetReference(self.reference, settings_changed=settings_changed)

	def handle_current_segment_changed_event(self):
		new_segment_ref = self.ExecuteScriptWithResult('last_segment_shown')
		if new_segment_ref:
			new_segment_ref = urllib.unquote(new_segment_ref)
			self.current_segment_changed(new_segment_ref)

	def current_segment_changed(self, new_segment_ref):
		pass

	def get_menu_items(self, event=None):
		def set_text():
			pane = self.aui_pane
			if not pane.IsShown():
				return _("Show the %s pane") % self.title
			else:
				return _("Hide the %s pane") % self.title

		extras = ()
		if self.is_hidable():
			extras += (
				(MenuItem(
					"Show this frame", # this is a dummy waiting for set_text
					self.toggle_frame, 
					update_text=set_text,
					doc=_("Shows or hides the pane")
				), IN_BOTH),
				(Separator, IN_BOTH),
			)

		extras += (
			(MenuItem(
				_("Search"), 
				self.search,
				doc=_("Search in this book")

			), IN_MENU),
			(Separator, IN_MENU),
		)
		
		items = extras + super(BookFrame, self).get_menu_items(event)
		if self.shows_info:
			items += (
			(Separator, IN_BOTH),
			(MenuItem(
				_("Information..."), 
				self.show_module_information,
				enabled=self.has_module,
				doc=_("Show information on the current book")
			), IN_BOTH),
		)

		return items
	
			
	def search(self):
		search_panel = self.get_search_panel_for_frame()
		assert search_panel, "Search panel not found for %s" % self
		search_panel.show()

	def search_quickly(self):
		qs = QuickSelector(self.get_window(), 
			title=_("Search for:"))

		qs.pseudo_modal(self.search_quickly_finished)
	
	def search_quickly_finished(self, qs, ansa):
		if ansa == wx.OK:
			search_panel = self.get_search_panel_for_frame()
			assert search_panel, "Search panel not found for %s" % self
			search_panel.search_and_show(qs.text)

		qs.Destroy()
			
	def has_module(self):
		return self.book.mod is not None
	
	def show_module_information(self):
		ModuleInfo(guiconfig.mainfrm, self.book.mod).ShowModal()

	def on_shown(self, shown=None):
		self.update_title(shown)
		
	def update_title(self, shown=None):
		if not self.reference:
			return

		m = guiconfig.mainfrm
		p = m.get_pane_for_frame(self)
		version = self.book.version
		ref = pysw.internal_to_user(self.reference)
		
		text = u"%s - %s (%s)" % (self.title, ref, version)
		m.set_pane_title(p.name, text)
	
	def get_search_panel_for_frame(self):
		for item in guiconfig.mainfrm.searchers:
			if self.book == item.book:
				return item

		return None		

	def get_frame_for_search(self):
		return self

	def focus_reference_textbox(self):
		textbox = self.get_reference_textbox()
		if textbox is None:
			return

		textbox.SetFocus()
		if hasattr(textbox, "SetSelection"):
			textbox.SetSelection(-1, -1)

	def get_reference_textbox(self):
		return None
		
	def go_quickly(self):
		qs = QuickSelector(self.get_window(), 
			title=_("Go to reference"))

		qs.pseudo_modal(self.go_quickly_finished)

	def open_tooltip(self, ref):
		tooltip = BiblicalPermanentTooltip(guiconfig.mainfrm,
			ref=pysw.internal_to_user(ref))

		tooltip.ShowTooltip(wx.GetMousePosition())
	
	def go_quickly_finished(self, qs, ansa):
		if ansa == wx.OK:
			ref = self.get_verified(qs.text)
			if ref:
				self.notify(ref, source=events.QUICK_SELECTOR)
			else:
				return

		qs.Destroy()

		# and move focus back to ourselves
		self.SetFocus()
	
	def get_verified(self, ref):
		return ref
	
	def format_ref(self, module, ref):
		return ref
	
class VerseKeyedFrame(BookFrame):
	def chapter_move(self, number):
		vk = VK(self.reference)
		vk.chapter += number
		if not vk.Error():
			self.notify(vk.text, source=events.CHAPTER_MOVE)
	
	def verse_move(self, number):
		vk = VK(self.reference)
		vk += number
		self.notify(vk.text, source=events.VERSE_MOVE)
	
	def get_actions(self):
		actions = super(VerseKeyedFrame, self).get_actions()
		actions.update({
			wx.WXK_F9 : self.verse_back,
		  	wx.WXK_F12: self.verse_forward,
			(wx.WXK_UP, wx.MOD_CMD): self.verse_back,
			(wx.WXK_DOWN, wx.MOD_CMD): self.verse_forward,
			# Emulation of vi, Gmail, Google Reader, etc.
			# Note that this overrides the next and previous chapter shortcut
			# from the book frame.
			ord("K"): self.verse_back,
			ord("J"): self.verse_forward,
		})

		return actions
	
		

		
	def verse_forward(self):
		"""Move forward a verse"""
		self.verse_move(1)
	
	def verse_back(self):
		"""Move back a verse"""
		self.verse_move(-1)
	
	def chapter_forward(self):
		"""Move to next chapter"""
		self.chapter_move(1)
	
	def chapter_back(self):
		"""Move to previous chapter"""
		self.chapter_move(-1)
	
	get_verified = BookFrame.get_verified_one_verse
	
	def format_ref(self, module, ref):
		return GetBestRange(ref, userOutput=True)

	def CheckChapterInBook(self, ref):
		if not self.book.mod:
			return True

		chapter_in_book = self.book.has_chapter(ref)
		if not chapter_in_book:
			self.reference = ref
			chapter_ref = pysw.UserVK(ref).get_book_chapter()
			self.SetPage(config.CHAPTER_NOT_IN_MODULE_MESSAGE() % chapter_ref)

		return chapter_in_book


class LinkedFrame(VerseKeyedFrame):
	def __init__(self, parent):
		self.panel = wx.Panel(parent)
		self.linked = False
		# This reference is set to the latest reference that should be
		# displayed.  If the pane is hidden then it will not have been
		# displayed.
		self.latest_reference = ""
		# True if the settings have changed since the pane was hidden.
		self.settings_changed = False
		super(LinkedFrame, self).__init__(self.panel)

		self.create_toolbar()
		sizer = wx.BoxSizer(wx.VERTICAL)
		si = sizer.Add(self.toolbar, flag=wx.GROW)
		sizer.SetItemMinSize(self.toolbar, self.toolbar.MinSize)
		sizer.Add(self, 3, flag=wx.GROW)
		self.panel.SetSizer(sizer)
		self.panel.Fit()

		guiconfig.mainfrm.bible_observers += self.bible_ref_changed
		
	
	def create_toolbar(self):
		self.toolbar = wx.ToolBar(self.panel, style=wx.TB_FLAT)
		self.create_toolbar_items()
		self.toolbar.Realize()
		self.toolbar.MinSize = self.toolbar.Size
	
	def create_toolbar_items(self):		
		self.gui_reference = versetree.VerseTree(self.toolbar,
									with_verses=True)
		self.gui_reference.SetSize((140, -1))
		
		self.gui_go = self.toolbar.AddTool(wx.ID_ANY,  
			guiutil.bmp("accept.png"),
			shortHelpString=_("Go to this reference"))

		self.toolbar.AddSeparator()
		
		self.gui_link = self.toolbar.AddCheckTool(
			wx.ID_ANY,
			guiutil.bmp("link.png"), 
			shortHelp=_("Link the %s to the Bible") % self.title
		)

		self.linked = True
		self.toolbar.ToggleTool(self.gui_link.Id, True)

		self.toolbar.InsertControl(0, self.gui_reference)
		
		

		self.toolbar.Bind(wx.EVT_TOOL, self.set_ref, id=self.gui_go.Id)
		self.toolbar.Bind(wx.EVT_TOOL, self.on_link, id=self.gui_link.Id)
		self.gui_reference.Bind(wx.EVT_TEXT_ENTER, self.set_ref)
		self.gui_reference.on_selected_in_tree += self.set_ref
		
	
	def set_ref(self, event):
		ref = self.gui_reference.Value
		if not ref: return
		ref = self.get_verified(ref)
		if not ref: return
		self.SetReference(ref)

	def SetReference(self, ref, settings_changed=False):
		self.latest_reference = ref
		# We only call SetReference when we are actually changing the window content.
		# As a result, we shouldn't have any stored up settings changes.
		self.settings_changed = False
		super(LinkedFrame, self).SetReference(ref, settings_changed=settings_changed)

	def get_ref_id(self, reference):
		osis_ref = VK(reference).getOSISRef()
		return super(LinkedFrame, self).get_ref_id(osis_ref)
	
	def on_link(self, event=None):
		self.linked = not self.linked
		if self.linked:
			self.notify(guiconfig.mainfrm.currentverse)
	
	def on_shown(self, shown=None):
		if shown and self.linked:
			if self.latest_reference != self.reference or self.settings_changed:
				self.notify(self.latest_reference, settings_changed=self.settings_changed)
		super(LinkedFrame, self).on_shown(shown)

	def bible_ref_changed(self, event):
		"""Logic must cover a few things:
		1. If the module is not linked, do not change reference.
		2. If settings have changed (and it's an important change), a forced reload is required.
		3. If the reference has changed, then we have to change the current
			reference if it is linked.
		"""
		latest_reference = event.ref if self.linked else self.latest_reference
		settings_changed = event.settings_changed and event.source not in events.sources_not_to_reload_linked_frames_for
		if self.aui_pane.IsShown():
			self.SetReference(latest_reference, settings_changed=settings_changed)
		else:
			self.latest_reference = event.ref
			self.settings_changed = settings_changed

	def get_window(self):
		return self.panel

	def refresh(self):
		self.SetReference(self.latest_reference, settings_changed=True)

class CommentaryFrame(LinkedFrame):
	id = N_("Commentary")

	def __init__(self, parent, book):
		super(CommentaryFrame, self).__init__(parent)
		self.SetBook(book)

	def SetReference(self, ref, settings_changed=False):
		if self.book.is_personal_commentary:
			self.reference = ref
			self.SetPage(config.PERSONAL_COMMENTARY_UNSUPPORTED_MESSAGE())
			return

		elif not self.CheckChapterInBook(ref):
			return

		super(CommentaryFrame, self).SetReference(ref, settings_changed=settings_changed)

		self.ChangeCurrentReference(ref)

	def ChangeCurrentReference(self, ref):
		self.gui_reference.SetValue(pysw.internal_to_user(ref))
		self.gui_reference.currentverse = ref

	def get_reference_textbox(self):
		return self.gui_reference

	def current_segment_changed(self, new_segment_ref):
		self.reference = VK(new_segment_ref).getText()
		self.latest_reference = self.reference
		self.ChangeCurrentReference(self.reference)
		self.update_title()
		
class DictionaryFrame(BookFrame):
	id = N_("Dictionary")

	def __init__(self, parent, book):
		self.dict = wx.Panel(parent)
		self.dictsplitter = wx.SplitterWindow(self.dict)
		
		super(DictionaryFrame, self).__init__(self.dictsplitter)
		self.SetBook(book)
		self.book.observers += self.dictionary_version_changed
		parent.on_close += lambda: \
			self.book.observers.remove(
				self.dictionary_version_changed
			)
		

		self.dictionary_list = DictionarySelector(self.dictsplitter, book)
		self.dictionary_list_index = -1
		self.dictionary_list.item_changed_observers += self.list_item_changed
		s = wx.BoxSizer(wx.HORIZONTAL)
		self.dictsplitter.SetSashGravity(1)
		self.dictsplitter.SplitVertically(self,
						self.dictionary_list)
		
		self.dictsplitter.SetMinimumPaneSize(100)
		
		def set_splitter():
			self.dictsplitter.SetSashPosition(self.dictsplitter.Size[0] - 130)

		wx.CallAfter(set_splitter)
						
		
		s.Add(self.dictsplitter, 1, wx.GROW)
		self.dict.SetSizer(s)
	
	def list_item_changed(self, event=None, suppress_reference_change=False):
		# Only force everything to reload if the list index has changed.
		dictionary_list_index = self.dictionary_list.list.GetFirstSelected()
		index_changed = (dictionary_list_index != self.dictionary_list_index)
		self.dictionary_list_index = dictionary_list_index
		if index_changed and not suppress_reference_change:
			self.UpdateUI()
			# If the user is in the middle of typing, then we don't want to steal focus from them.
			# Otherwise, we need to steal focus to fix the list problem.
			self.ForceKillFocus()
			if self.dictionary_list.item_to_focus_on is not self.dictionary_list.text_entry:
				self.SetFocus()
			#if self.dictionary_list.item_to_focus_on:
			#	self.ForceKillFocus()

	def chapter_move(self, amount):
		mod = self.book.mod
		if not mod:
			return

		key = mod.getKey()
		key.Persist(1)
		key.setText(to_str(self.reference, mod))
		mod.setKey(key)
		mod.increment(amount);
		ref = to_unicode(mod.getKeyText(), mod)
		self.notify(ref, source=events.CHAPTER_MOVE)
	
	def update_title(self, shown=None):
		m = guiconfig.mainfrm
		p = m.get_pane_for_frame(self)
		version = self.book.version
		ref = self.reference
		ref = self.format_ref(self.book.mod, ref)

		text = u"%s - %s (%s)" % (self.title, ref, version)
		m.set_pane_title(p.name, text)
	
	def format_ref(self, module, ref):
		return self.book.format_ref(module, ref)
		
	def get_window(self):
		return self.dict
		
	
	def dictionary_version_changed(self, newversion):
		freeze_ui = guiutil.FreezeUI(self.dictionary_list)
		self.dictionary_list.set_book(self.book)
		self.dictionary_list_index = -1
	
	def notify(self, ref, source=None, settings_changed=False):
		self.UpdateUI(ref)

	def UpdateUI(self, ref=""):
		if not ref:
			ref = self.dictionary_list.GetValue().upper()
		else:
			self.dictionary_list.choose_item(ref, update_text_entry_value=True)

		self.SetReference(ref)

	@guiutil.frozen
	def SetReference(self, ref, settings_changed=False):
		if not ref:
			# Initially, we start with no reference.
			# Since this causes an exception in the protocol handler,
			# we just force it to be the first available topic.
			topics = self.book.GetTopics()
			if topics:
				ref = topics[0].upper()

		super(DictionaryFrame, self).SetReference(ref, settings_changed=settings_changed)

	def SetReference_from_string(self, string):
		wx.CallAfter(self.UpdateUI, string)

	def get_reference_textbox(self):
		return self.dictionary_list.text_entry

	def current_segment_changed(self, new_segment_ref):
		# If the current segment changes as a result of the user typing in
		# the text box, we want to leave the text as they typed it rather
		# than replacing it with the full name of the current topic.
		if wx.Window.FindFocus() == self.dictionary_list.text_entry.text:
			return

		self.dictionary_list.choose_item(new_segment_ref, update_text_entry_value=True, suppress_reference_change=True)
		self.reference = new_segment_ref
		self.update_title()
