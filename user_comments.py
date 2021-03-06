import wx
from protocols import protocol_handler
from tooltip import TooltipConfig
from tag_passage_dialog import edit_comment
import events
import guiconfig
from gui import guiutil
from passage_list import lookup_passage_entry, get_primary_passage_list_manager
from backend.bibleinterface import biblemgr
from util.string_util import text2html

def on_usercomment_opened(frame, href, url):
	passage_entry = find_passage_entry(url)

	# hide all tooltips - particularly the user comments one
	guiconfig.mainfrm.hide_tooltips()

	# now we do a calllater rather than callafter - launching modal dialogs
	# from here needs a bit of care, otherwise we can end up in a nasty state
	wx.CallLater(150, edit_comment, frame, passage_entry)

def on_usercomment_hover(frame, href, url, element, x, y):
	passage_entry = find_passage_entry(url)
	tooltip_config = UserCommentTooltipConfig(passage_entry)
	frame.show_tooltip(tooltip_config)

protocol_handler.register_handler("usercomment", on_usercomment_opened)
protocol_handler.register_hover("usercomment", on_usercomment_hover)

def find_passage_entry(url):
	comment_id = int(url.getHostName())
	return lookup_passage_entry(comment_id)

class UserCommentTooltipConfig(TooltipConfig):
	def __init__(self, passage_entry):
		super(UserCommentTooltipConfig, self).__init__(book=biblemgr.bible)
		self.passage_entry = passage_entry

	def add_to_toolbar(self, toolbar, permanent):
		toolbar.gui_edit = toolbar.AddLabelTool(
			wx.ID_ANY, 
			_("Edit"),
			guiutil.bmp("page_edit.png"),
			shortHelp=_("Edit this comment"))

		toolbar.gui_delete = toolbar.AddLabelTool(wx.ID_ANY, 
			_("Delete"),
			guiutil.bmp("delete.png"),
			shortHelp=_("Delete this comment"))

	def bind_to_toolbar(self, toolbar):
		toolbar.Bind(
			wx.EVT_TOOL,
			self.do_delete_comment,
			id=toolbar.gui_delete.Id
		)

		toolbar.Bind(
			wx.EVT_TOOL,
			self.do_edit_comment,
			id=toolbar.gui_edit.Id
		)


	def get_title(self):
		return _(u'Comment on %s') % self.localised_reference

	def get_text(self):
		reference = (u'<b><a href="bible:%s">%s</a></b>'
				% (str(self.passage_entry), text2html(self.localised_reference)))
		comment = text2html(self.passage_entry.comment)
		return u'<p>%(reference)s</p><p>%(comment)s</p>' % locals()

	@property
	def localised_reference(self):
		return self.passage_entry.passage.GetBestRange(userOutput=True)

	def do_edit_comment(self, event):
		self.hide_tooltip()
		edit_comment(guiconfig.mainfrm, self.passage_entry)

	def do_delete_comment(self, event):
		delete_comment = wx.MessageBox(
			_("Are you sure you want to delete this comment?"),
			_("Delete Comment"), 
			wx.YES_NO,
			parent=None)

		if delete_comment == wx.YES:
			self.hide_tooltip()
			self.passage_entry.parent.remove_passage(self.passage_entry)
			get_primary_passage_list_manager().save()
