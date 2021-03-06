from django.conf.urls import patterns, include, url
from django.contrib import admin
from accounts.views import alogout,alogin,register,index
from side.views import *
from talents.views import *
from talents import views
urlpatterns = [
    # Examples:
    # url(r'^$', 'project.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    #url(r'^talents/','talents.views.talents',name='talents'),
    url(r'^pending_application/','talents.views.pending_application',name='pending_application'),
    url(r'^handing/(?P<position_id>[^/]+)/$','talents.views.handing',name='handing'),
    url(r'^exrecord/(?P<position_id>[^/]+)/$','talents.views.exrecord',name='exrecord'),
    url(r'^positionmanage/','talents.views.position',name='position'),
    url(r'^positionform','talents.views.positionform',name='positionform'),
    url(r'^job_positions/new/','talents.views.positionform',name='positionnew'),
    url(r'^resumemanage/','talents.views.resumemanage',name='resumemanage'),   
    url(r'^copy_position/(?P<position_id>[^/]+)/$','talents.views.copy_position',name='copy_position'),
    url(r'^positionprofile/(?P<position_id>[^/]+)/$','talents.views.positionprofile',name='positionprofile'),
    url(r'^agree_application/(?P<position_id>[^/]+)/$','talents.views.agree_application',name='agree_application'),
    url(r'^disagree_application/(?P<position_id>[^/]+)/$','talents.views.disagree_application',name='disagree_application'),
    url(r'^set_Email/(?P<position_id>[^/]+)/$','talents.views.set_Email',name='set_Email'),
    url(r'^update_position/(?P<position_id>[^/]+)/$','talents.views.update_position',name='update_position'),
    url(r'^handleingposition/','talents.views.handleingposition',name='handleingposition'),
    url(r'^examine/(?P<position_id>[^/]+)/$','talents.views.examine',name='examine'),
    url(r'^handleposition/','talents.views.handleposition',name='handleposition'),
    url(r'^filing/','talents.views.filing'),
    url(r'^delete/(?P<resume_id>[^/]+)/$','talents.views.delete',name='delete'),
    url(r'^positiontask1/(?P<position_id>[^/]+)/$','talents.views.positiontask1',name='positiontask1'),
    url(r'^positiontask/','talents.views.positiontask',name='positiontask'), 
    url(r'^talent_pool','talents.views.talents_pool',name='talent_pool'), 
    url(r'^resumesearch/','talents.views.resumemanage',name='resumesearch'),
    url(r'^search_talentform/','talents.views.search_talentform'),
    url(r'^input_pool/(?P<resume_id>[^/]+)/$','talents.views.input_pool',name='input_pool'),
    url(r'^suitresume/','talents.views.find_suitable',name='suitresume'),
    url(r'^suitresume_search','talents.views.suitresume_search',name='suitresume_search'),
    url(r'^first_page/','talents.views.first_page',name='first_page'),
    url(r'^position_search_form/','talents.views.position_search_form',name='position_search_form'),  
    url(r'^Filing_search_form/','talents.views.Filing_search_form',name='Filing_search_form'),  
    url(r'^resume_sort/(?P<id>[^/]+)/$','talents.views.resume_sort',name='resume_sort'),
    url(r'^cancel_position/(?P<position_id>[^/]+)/$','talents.views.cancel_position',name='cancel_position'),
    url(r'^publish_position/(?P<position_id>[^/]+)/$','talents.views.publish_position',name='publish_position'),
    url(r'^publishing_position/','talents.views.publishing_position',name='publishing_position'),
    url(r'^handledposition/','talents.views.handledposition',name='handledposition'),
    url(r'^recover_examine/(?P<position_id>[^/]+)/$','talents.views.recover_examine',name='recover_examine'),
]




