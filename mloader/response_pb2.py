# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: response.proto
# Protobuf Python Version: 4.25.3
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0eresponse.proto\x12\x05manga\"P\n\x06\x42\x61nner\x12\x11\n\timage_url\x18\x01 \x01(\t\x12\'\n\x06\x61\x63tion\x18\x02 \x01(\x0b\x32\x17.manga.TransitionAction\x12\n\n\x02id\x18\x03 \x01(\r\"B\n\nBannerList\x12\x14\n\x0c\x62\x61nner_title\x18\x01 \x01(\t\x12\x1e\n\x07\x62\x61nners\x18\x02 \x03(\x0b\x32\r.manga.Banner\"/\n\x10TransitionAction\x12\x0e\n\x06method\x18\x01 \x01(\x05\x12\x0b\n\x03url\x18\x02 \x01(\t\"\xc9\x01\n\x07\x43hapter\x12\x10\n\x08title_id\x18\x01 \x01(\r\x12\x12\n\nchapter_id\x18\x02 \x01(\r\x12\x0c\n\x04name\x18\x03 \x01(\t\x12\x11\n\tsub_title\x18\x04 \x01(\t\x12\x15\n\rthumbnail_url\x18\x05 \x01(\t\x12\x17\n\x0fstart_timestamp\x18\x06 \x01(\r\x12\x15\n\rend_timestamp\x18\x07 \x01(\r\x12\x16\n\x0e\x61lready_viewed\x18\x08 \x01(\x08\x12\x18\n\x10is_vertical_only\x18\t \x01(\x08\"\xa8\x01\n\x0c\x43hapterGroup\x12\x17\n\x0f\x63hapter_numbers\x18\x01 \x01(\t\x12*\n\x12\x66irst_chapter_list\x18\x02 \x03(\x0b\x32\x0e.manga.Chapter\x12(\n\x10mid_chapter_list\x18\x03 \x03(\x0b\x32\x0e.manga.Chapter\x12)\n\x11last_chapter_list\x18\x04 \x03(\x0b\x32\x0e.manga.Chapter\"\xdd\x01\n\x07\x43omment\x12\n\n\x02id\x18\x01 \x01(\r\x12\r\n\x05index\x18\x02 \x01(\r\x12\x11\n\tuser_name\x18\x03 \x01(\t\x12\x10\n\x08icon_url\x18\x04 \x01(\t\x12\x1a\n\ris_my_comment\x18\x06 \x01(\x08H\x00\x88\x01\x01\x12\x1a\n\ralready_liked\x18\x07 \x01(\x08H\x01\x88\x01\x01\x12\x17\n\x0fnumber_of_likes\x18\t \x01(\r\x12\x0c\n\x04\x62ody\x18\n \x01(\t\x12\x0f\n\x07\x63reated\x18\x0b \x01(\rB\x10\n\x0e_is_my_commentB\x10\n\x0e_already_liked\"\xfa\x03\n\rAdNetworkList\x12\x33\n\x0b\x61\x64_networks\x18\x01 \x01(\x0b\x32\x1e.manga.AdNetworkList.AdNetwork\x1a\xb3\x03\n\tAdNetwork\x12\x39\n\x08\x66\x61\x63\x65\x62ook\x18\x01 \x01(\x0b\x32\'.manga.AdNetworkList.AdNetwork.Facebook\x12\x33\n\x05\x61\x64mob\x18\x02 \x01(\x0b\x32$.manga.AdNetworkList.AdNetwork.Admob\x12\x33\n\x05mopub\x18\x03 \x01(\x0b\x32$.manga.AdNetworkList.AdNetwork.Mopub\x12\x37\n\x07\x61\x64sense\x18\x04 \x01(\x0b\x32&.manga.AdNetworkList.AdNetwork.Adsense\x12\x39\n\x08\x61pplovin\x18\x05 \x01(\x0b\x32\'.manga.AdNetworkList.AdNetwork.Applovin\x1a \n\x08\x46\x61\x63\x65\x62ook\x12\x14\n\x0cplacement_id\x18\x01 \x01(\t\x1a\x18\n\x05\x41\x64mob\x12\x0f\n\x07unit_id\x18\x01 \x01(\t\x1a\x18\n\x05Mopub\x12\x0f\n\x07unit_id\x18\x01 \x01(\t\x1a\x1a\n\x07\x41\x64sense\x12\x0f\n\x07unit_id\x18\x01 \x01(\t\x1a\x1b\n\x08\x41pplovin\x12\x0f\n\x07unit_id\x18\x01 \x01(\t\"\xb8\x04\n\x05Popup\x12*\n\nos_default\x18\x01 \x01(\x0b\x32\x16.manga.Popup.OSDefault\x12,\n\x0b\x61pp_default\x18\x02 \x01(\x0b\x32\x17.manga.Popup.AppDefault\x12.\n\x0cmovie_reward\x18\x03 \x01(\x0b\x32\x18.manga.Popup.MovieReward\x1a?\n\x06\x42utton\x12\x0c\n\x04text\x18\x01 \x01(\t\x12\'\n\x06\x61\x63tion\x18\x02 \x01(\x0b\x32\x17.manga.TransitionAction\x1a\xab\x01\n\tOSDefault\x12\x0f\n\x07subject\x18\x01 \x01(\t\x12\x0c\n\x04\x62ody\x18\x02 \x01(\t\x12&\n\tok_button\x18\x03 \x01(\x0b\x32\x13.manga.Popup.Button\x12+\n\x0eneutral_button\x18\x04 \x01(\x0b\x32\x13.manga.Popup.Button\x12*\n\rcancel_button\x18\x05 \x01(\x0b\x32\x13.manga.Popup.Button\x1ag\n\nAppDefault\x12\x0f\n\x07subject\x18\x01 \x01(\t\x12\x0c\n\x04\x62ody\x18\x02 \x01(\t\x12\'\n\x06\x61\x63tion\x18\x03 \x01(\x0b\x32\x17.manga.TransitionAction\x12\x11\n\timage_url\x18\x04 \x01(\t\x1aM\n\x0bMovieReward\x12\x11\n\timage_url\x18\x01 \x01(\t\x12+\n\radvertisement\x18\x02 \x01(\x0b\x32\x14.manga.AdNetworkList\"\x95\x02\n\x08LastPage\x12\'\n\x0f\x63urrent_chapter\x18\x01 \x01(\x0b\x32\x0e.manga.Chapter\x12$\n\x0cnext_chapter\x18\x02 \x01(\x0b\x32\x0e.manga.Chapter\x12$\n\x0ctop_comments\x18\x03 \x03(\x0b\x32\x0e.manga.Comment\x12\x15\n\ris_subscribed\x18\x04 \x01(\x08\x12\x16\n\x0enext_timestamp\x18\x05 \x01(\r\x12\x14\n\x0c\x63hapter_type\x18\x06 \x01(\x05\x12+\n\radvertisement\x18\x07 \x01(\x0b\x32\x14.manga.AdNetworkList\x12\"\n\x0cmovie_reward\x18\x08 \x01(\x0b\x32\x0c.manga.Popup\"c\n\tMangaPage\x12\x11\n\timage_url\x18\x01 \x01(\t\x12\r\n\x05width\x18\x02 \x01(\r\x12\x0e\n\x06height\x18\x03 \x01(\r\x12\x0c\n\x04type\x18\x04 \x01(\x05\x12\x16\n\x0e\x65ncryption_key\x18\x05 \x01(\t\"\xa5\x01\n\x04Page\x12$\n\nmanga_page\x18\x01 \x01(\x0b\x32\x10.manga.MangaPage\x12&\n\x0b\x62\x61nner_list\x18\x02 \x01(\x0b\x32\x11.manga.BannerList\x12\"\n\tlast_page\x18\x03 \x01(\x0b\x32\x0f.manga.LastPage\x12+\n\radvertisement\x18\x04 \x01(\x0b\x32\x14.manga.AdNetworkList\" \n\x03Sns\x12\x0c\n\x04\x62ody\x18\x01 \x01(\t\x12\x0b\n\x03url\x18\x02 \x01(\t\"\x84\x02\n\x0bMangaViewer\x12\x1a\n\x05pages\x18\x01 \x03(\x0b\x32\x0b.manga.Page\x12\x12\n\nchapter_id\x18\x02 \x01(\r\x12 \n\x08\x63hapters\x18\x03 \x03(\x0b\x32\x0e.manga.Chapter\x12\x17\n\x03sns\x18\x04 \x01(\x0b\x32\n.manga.Sns\x12\x12\n\ntitle_name\x18\x05 \x01(\t\x12\x14\n\x0c\x63hapter_name\x18\x06 \x01(\t\x12\x1a\n\x12number_of_comments\x18\x07 \x01(\r\x12\x18\n\x10is_vertical_only\x18\x08 \x01(\x08\x12\x10\n\x08title_id\x18\t \x01(\r\x12\x18\n\x10start_from_right\x18\n \x01(\x08\"\x96\x01\n\x05Title\x12\x10\n\x08title_id\x18\x01 \x01(\r\x12\x0c\n\x04name\x18\x02 \x01(\t\x12\x0e\n\x06\x61uthor\x18\x03 \x01(\t\x12\x1a\n\x12portrait_image_url\x18\x04 \x01(\t\x12\x1b\n\x13landscape_image_url\x18\x05 \x01(\t\x12\x12\n\nview_count\x18\x06 \x01(\r\x12\x10\n\x08language\x18\x07 \x01(\x05\"\xce\x04\n\x0fTitleDetailView\x12\x1b\n\x05title\x18\x01 \x01(\x0b\x32\x0c.manga.Title\x12\x17\n\x0ftitle_image_url\x18\x02 \x01(\t\x12\x10\n\x08overview\x18\x03 \x01(\t\x12\x1c\n\x14\x62\x61\x63kground_image_url\x18\x04 \x01(\t\x12\x16\n\x0enext_timestamp\x18\x05 \x01(\r\x12\x15\n\rupdate_timing\x18\x06 \x01(\x05\x12\"\n\x1aviewing_period_description\x18\x07 \x01(\t\x12\x1b\n\x13non_appearance_info\x18\x08 \x01(\t\x12*\n\x12\x66irst_chapter_list\x18\t \x03(\x0b\x32\x0e.manga.Chapter\x12)\n\x11last_chapter_list\x18\n \x03(\x0b\x32\x0e.manga.Chapter\x12\x1e\n\x07\x62\x61nners\x18\x0b \x03(\x0b\x32\r.manga.Banner\x12,\n\x16recommended_title_list\x18\x0c \x03(\x0b\x32\x0c.manga.Title\x12\x17\n\x03sns\x18\r \x01(\x0b\x32\n.manga.Sns\x12\x19\n\x11is_simul_released\x18\x0e \x01(\x08\x12\x15\n\ris_subscribed\x18\x0f \x01(\x08\x12\x0e\n\x06rating\x18\x10 \x01(\x05\x12\x1b\n\x13\x63hapters_descending\x18\x11 \x01(\x08\x12\x17\n\x0fnumber_of_views\x18\x12 \x01(\r\x12/\n\x12\x63hapter_list_group\x18\x1c \x03(\x0b\x32\x13.manga.ChapterGroup\"l\n\rSuccessResult\x12\x31\n\x11title_detail_view\x18\x08 \x01(\x0b\x32\x16.manga.TitleDetailView\x12(\n\x0cmanga_viewer\x18\n \x01(\x0b\x32\x12.manga.MangaViewer\"1\n\x08Response\x12%\n\x07success\x18\x01 \x01(\x0b\x32\x14.manga.SuccessResultB\x0fH\x01Z\x0bmanga/protob\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'response_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  _globals['DESCRIPTOR']._options = None
  _globals['DESCRIPTOR']._serialized_options = b'H\001Z\013manga/proto'
  _globals['_BANNER']._serialized_start=25
  _globals['_BANNER']._serialized_end=105
  _globals['_BANNERLIST']._serialized_start=107
  _globals['_BANNERLIST']._serialized_end=173
  _globals['_TRANSITIONACTION']._serialized_start=175
  _globals['_TRANSITIONACTION']._serialized_end=222
  _globals['_CHAPTER']._serialized_start=225
  _globals['_CHAPTER']._serialized_end=426
  _globals['_CHAPTERGROUP']._serialized_start=429
  _globals['_CHAPTERGROUP']._serialized_end=597
  _globals['_COMMENT']._serialized_start=600
  _globals['_COMMENT']._serialized_end=821
  _globals['_ADNETWORKLIST']._serialized_start=824
  _globals['_ADNETWORKLIST']._serialized_end=1330
  _globals['_ADNETWORKLIST_ADNETWORK']._serialized_start=895
  _globals['_ADNETWORKLIST_ADNETWORK']._serialized_end=1330
  _globals['_ADNETWORKLIST_ADNETWORK_FACEBOOK']._serialized_start=1189
  _globals['_ADNETWORKLIST_ADNETWORK_FACEBOOK']._serialized_end=1221
  _globals['_ADNETWORKLIST_ADNETWORK_ADMOB']._serialized_start=1223
  _globals['_ADNETWORKLIST_ADNETWORK_ADMOB']._serialized_end=1247
  _globals['_ADNETWORKLIST_ADNETWORK_MOPUB']._serialized_start=1249
  _globals['_ADNETWORKLIST_ADNETWORK_MOPUB']._serialized_end=1273
  _globals['_ADNETWORKLIST_ADNETWORK_ADSENSE']._serialized_start=1275
  _globals['_ADNETWORKLIST_ADNETWORK_ADSENSE']._serialized_end=1301
  _globals['_ADNETWORKLIST_ADNETWORK_APPLOVIN']._serialized_start=1303
  _globals['_ADNETWORKLIST_ADNETWORK_APPLOVIN']._serialized_end=1330
  _globals['_POPUP']._serialized_start=1333
  _globals['_POPUP']._serialized_end=1901
  _globals['_POPUP_BUTTON']._serialized_start=1480
  _globals['_POPUP_BUTTON']._serialized_end=1543
  _globals['_POPUP_OSDEFAULT']._serialized_start=1546
  _globals['_POPUP_OSDEFAULT']._serialized_end=1717
  _globals['_POPUP_APPDEFAULT']._serialized_start=1719
  _globals['_POPUP_APPDEFAULT']._serialized_end=1822
  _globals['_POPUP_MOVIEREWARD']._serialized_start=1824
  _globals['_POPUP_MOVIEREWARD']._serialized_end=1901
  _globals['_LASTPAGE']._serialized_start=1904
  _globals['_LASTPAGE']._serialized_end=2181
  _globals['_MANGAPAGE']._serialized_start=2183
  _globals['_MANGAPAGE']._serialized_end=2282
  _globals['_PAGE']._serialized_start=2285
  _globals['_PAGE']._serialized_end=2450
  _globals['_SNS']._serialized_start=2452
  _globals['_SNS']._serialized_end=2484
  _globals['_MANGAVIEWER']._serialized_start=2487
  _globals['_MANGAVIEWER']._serialized_end=2747
  _globals['_TITLE']._serialized_start=2750
  _globals['_TITLE']._serialized_end=2900
  _globals['_TITLEDETAILVIEW']._serialized_start=2903
  _globals['_TITLEDETAILVIEW']._serialized_end=3493
  _globals['_SUCCESSRESULT']._serialized_start=3495
  _globals['_SUCCESSRESULT']._serialized_end=3603
  _globals['_RESPONSE']._serialized_start=3605
  _globals['_RESPONSE']._serialized_end=3654
# @@protoc_insertion_point(module_scope)
