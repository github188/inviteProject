# -*- coding: utf-8 -*-
''' 
@author: 张茗    
@contact: zhangming@nantian.com.cn 
@note: Resume management system,The last modification time:2016.1.27       
'''
from django.template import loader,Context,RequestContext
from django.shortcuts import render
from django.http import HttpResponse
import poplib
import re
import codecs
import json
from django.core import serializers
from email.parser import Parser
from email.header import decode_header
from email.utils import parseaddr
import sgmllib,sys,os,string
from talents.models import Position 
from resume.models import Resume,Repeat_Resume,import_ID,fail_import_id,importid_group
from manager.models import Cor_role_user_depart,Roles,Department,Power,Cor_user_Power
import  threading,time
from django.template.context_processors import request
from accounts.models import MyUser
from resume.parser_51 import parser_with_51 
from resume.parser_zhilian import parser_with_zhilian 
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.core.paginator import PageNotAnInteger
from django.core.paginator import EmptyPage
from _mysql import NULL
from project import settings
from talents.views import sentmail,get_depart
import django.utils.timezone as timezone  

# from resume.models import User,Position,Resume,Interview
tagstack = []
info_list = []
resume_info={'path':'','registered_addr':'','name':'', 'sex':'', 'age':'', 'work_experience':'', 'now_addr':'', 'id':'', 'phone':'', 'E-mail':'', 'education':'','marital':''}
Subject = []
txt =[]
Date = []
def send_back(dict_info,user):
    '''上传简历失败，自动退回相应ID的简历下载请求
        dict_info:简历基本信息
        user:执行操作的用户'''
    ISOTIMEFORMAT='%Y-%m-%d %X'
    now_time = time.strftime( ISOTIMEFORMAT, time.localtime() )
    ID_objs = import_ID.objects.filter(resume_id = dict_info['id'])
    if ID_objs:
        for ID_obj in ID_objs:
            ID_obj.Status=1
            ID_obj.UploaderID = user
            ID_obj.remark='用户'+user.username+'于'+now_time+'上传，指定用户'+user.username+'锁定'
            ID_obj.save()
        
def separat():
    '''获取当前系统的分隔符'''
    if len(settings.MEDIA_ROOT.split('\\'))>1:
        separator = '\\'
    else :
        separator = '/'
    return separator
def down_file(request,filename):
    filename = filename.encode('UTF-8')
    separator = separat()
    name_list = filename.split(separator)
    filePath = os.path.join(settings.MEDIA_ROOT,name_list[-2] ,name_list[-1])
    if os.path.exists(filePath):
        f =open(filePath,'r')
        data = f.read()
        f.close()
        response = HttpResponse(data,content_type='application/octet-stream') 
        response['Content-Disposition'] = 'attachment; filename=%s' % name_list[-1]
        return response
    else:
        return HttpResponse('该文件不存在!')
def find_depart(depart,depart_list):
    if not depart:
        return 0
    if depart not in depart_list:
        depart = depart.superior_department        
        result = find_depart(depart,depart_list)
        if result:
            return 1
        else:
            return 0 
    else:
        return 1

def check_group(user):
    '''
    检查ID的状态
    '''
    idgroup_list =[]
    idgroups = importid_group.objects.filter(Status = 0).order_by("-id")
    for idgroup in idgroups:
        IDs = import_ID.objects.filter(groupid=idgroup).filter(Status=0).order_by("-id")
        if len(IDs)==0:
            idgroup.Status=1
            idgroup.save()
        else:
            departs = get_depart(user)
            if find_depart(idgroup.DepartID,departs):
                idgroup_list.append(idgroup)
    return idgroup_list
    
def chack_id():
    '''
        检查需要下载的ID，在系统中是否已存在
    '''
    inters = []
    #数据
    lock_user_id = import_ID.objects.filter(Status=0).order_by("-id")
    for s in lock_user_id:           
        inter = Resume.objects.filter(SearchID=s.resume_id)
        if len(inter)==0:           
            inters.append(s)
        else:
            for resume in inter:
                if not resume.UserID:
                    select_name = MyUser.objects.filter(username=s.user_name)
                    for uname in select_name:
                        resume.UserID= uname
                        resume.save()
                        s.Status=1
                        s.remark = '本简历已存在于系统中，且无人锁定，系统已自动帮您锁定'
                        s.save()
    return inters
def filter_education(content):
    '''进行学历过滤'''
    if txt[0].find('博士')!= -1:
        edu = '4博士'
    elif txt[0].find('硕士') != -1:
        edu = '3硕士'
    elif txt[0].find('研究生') != -1:
        edu = '3研究生'
    elif txt[0].find('本科') != -1:        
        edu = '2本科'
    elif  txt[0].find('大专')!=-1:
        edu = '1大专'
    else:
        edu = '0其他'
    if edu:
        resume_info['education'] = edu
    if content.find('高中')!=-1 or content.find('初中')!=-1 or content.find('小学')!=-1 or content.find('中专')!=-1:
        return -1
    else:
        return 1
@login_required
def updata_resume(request,resumeid):
    '''导入未知格式的简历，简历基本信息由上传者提供'''
    #cookie
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user = UserModel.objects.get(id = user_id)
    resume_obj = Resume.objects.get(id = resumeid)
    if request.method == "POST":
        user_obj=""
        index=0
        errors=[]
        separator = separat()
        
        #------------------获取表单信息-----------------------

        files = request.FILES.getlist('headImg')#FILES的类型是〃<type 'list'>需要遍历取出每一个file
        resu_name = request.POST['name']
        resu_six = request.POST['sex']
        resu_age = request.POST['age']
        resu_experence = request.POST['experience']
        resu_position = request.POST['position']
        resu_phone = request.POST['phone']
        resu_mail = request.POST['mail']
        resu_edu = request.POST['edu']
        
        #------------------获取表单信息-----------------------
        
        #--------------------------------处理表单数据---------------------------------------
        for f in files:          
            for chunk in f.chunks():
                addr_split = resume_obj.Addr.split(separator)
                new_resume = open(os.path.join(settings.MEDIA_ROOT,addr_split[-2].encode('UTF-8') , addr_split[-1].encode('UTF-8')),'w')
                chunk = chunk.replace('gb2312','utf-8')
                if f.name.find('.htm') == -1:
                    new_resume.write(chunk)
                else:
                    try:
                        new_resume.write(chunk.decode('gb2312').encode('UTF-8'))
                    except:
                        new_resume.write(chunk)
                    finally:
                        pass
                new_resume.close()
            index = index+1
        if resu_name:
            resume_obj.CandidateName = resu_name;
            index = index+1
        if resu_six:
            resume_obj.CandidateSex = resu_six;
            index = index+1
        if resu_age:
            resume_obj.CandidateAge = resu_age;
            index = index+1
        if resu_experence:
            resume_obj.CandidateProfile = resu_experence;
            index = index+1
        if resu_position:
            resume_obj.PositionName = resu_position;
            index = index+1
        if resu_phone:
            resume_obj.CandidatePhone = resu_phone;
            index = index+1
        if resu_mail:
            resume_obj.CandidateEmail = resu_mail;
            index = index+1
        if resu_edu:
            if resu_edu == '本科':
                resu_edu = '2本科'
            elif resu_edu == '大专':
                resu_edu = '1大专'
            elif resu_edu == '研究生' or resu_edu == '硕士':
                resu_edu = '3硕士'
            elif resu_edu == '博士':
                resu_edu = '4博士'
            else:
                resu_edu = '0其他'
            resume_obj.Candidate_edu = resu_edu;
            index = index+1
        resume_obj.save()    
        if index>0:
            resume_obj.Time = timezone.now()
            resume_obj.save()
            return HttpResponse('更新成功!')
        else:
            errors.append('请填写要修改的项')
            return render(request, 'updata_resume.html',{'user':user,'resume':resume_obj,'errors':errors})
        #--------------------------------处理表单数据---------------------------------------
          
    else:
        return render(request, 'updata_resume.html',{'user':user,'resume':resume_obj})
@login_required
def manage_importedid(request):
    '''管理某个还有需要下载的ID的ID组
    id_list:前端传回所有选中的ID，分离后保存在列表id_list中
    '''
    error=[]
    refresh =[]
    id_list = []
    #cookie
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user = UserModel.objects.get(id = user_id)
    gruopID  = request.GET['id']
    idguoup_obj = importid_group.objects.get(id = int(gruopID))
    ID_infoes = import_ID.objects.filter(groupid = idguoup_obj).filter(Status = 0)
    
#     ID  = request.GET['id']
#     ID_info = import_ID.objects.get(id = ID)
    if request.method == "POST":
        allid = request.POST['allid']
        if allid == '':
            error.append('请选着要处理的ID号')
            return render(request, 'manage_importedid.html',{'user':user,'ID_infoes':ID_infoes,'gruop':idguoup_obj,'error':error})
        else:
            id_list = allid.split('|')
        remark = request.POST['remark'] 
        for ID in id_list[1:]:         
            ID_info = import_ID.objects.get(id = ID)           
            ID_info.remark = remark
            ID_info.Status = 2
            ID_info.UploaderID = user 
            ID_info.save()
            refresh.append('ok')
        idgroups = check_group(user)
    
        t = loader.get_template("check_idgroup.html")
        c = Context({'idgroups':idgroups,'refresh':refresh})
        return HttpResponse(t.render(c))
    else:
        return render(request, 'manage_importedid.html',{'user':user,'ID_infoes':ID_infoes,'gruop':idguoup_obj})
@login_required
def ownimport_id(request):
    '''查看自己导入的ID'''
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user = UserModel.objects.get(id = user_id)
    #检查需要下载ID，在系统中是否已存在
    chack_id()
    
    id_list = import_ID.objects.filter(referrerID = user).order_by("-id")
    t = loader.get_template("ownimport_id.html")
    c = Context({'id_list':id_list})
    return HttpResponse(t.render(c))
    return render(request, 'ownimport_id.html',)
@login_required
def id_processed(request):
    '''查看用户处理过的ID，包括完成的和退回的'''
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user = UserModel.objects.get(id = user_id)
    #检查需要下载ID，在系统中是否已存在
    chack_id()
    
    id_list = import_ID.objects.filter( UploaderID = user).order_by("-id")
   
    t = loader.get_template("id_processed.html")
    c = Context({'id_list':id_list})
    return HttpResponse(t.render(c))
    return render(request, 'id_processed.html',)
def all_user(request):
    '''获取所有的用户姓名'''
    all_user_obj = MyUser.objects.all().exclude(is_active = 0)
    str_user = ""
    for user in all_user_obj:
        str_user += user.username+";"   
    return HttpResponse(str_user)

def import_choice(request):
    '''选择导入的简历是否是系统能解析的'''
    return render(request, 'import_choice.html')
def work_experience_switch(work_experience):
    '''格式化输出工作年限（目前要求只留下数字）
        Args:
            work_experience:从简历中拿到的字符串。例如：5年工作经验
        return:
            work_experience:拿到的字符串只取整数，若没有数字则取0
    '''
    m = re.match(r'^[\s\S]*?([0-9]+)[\s\S]*?$',work_experience)
    if m!=None:
        work_experience = m.group(1)
        return int(work_experience)
    else:
        return 0
#         if work_experience:
#             return 0
#         else:
#             return 
@login_required    
def import_resume2(request):
    '''导入未知格式的简历，简历基本信息由上传者提供'''
    errors = []
    refresh = []
    #cookie
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user = UserModel.objects.get(id = user_id)
    recruiter_roleID=Power.objects.filter(name="简历筛选权")   
    recruiters =   Cor_user_Power.objects.filter(PowerID=recruiter_roleID).exclude(UserID__is_active = 0) 
    if request.method == "POST":
        user_obj=""
        filename=''
        separator = separat()
        #------------------获取表单信息-----------------------
        belong = request.POST['fromStationText']
        if belong == '':
            errors.append('简历归属人')
            return render(request, 'import_resume2.html',{'user':user,'recruiters':recruiters,'errors':errors,'refresh':refresh})
        user_obj = MyUser.objects.get(username=belong)#朝找resu_name的对象         
        files = request.FILES.getlist('headImg')#FILES的类型是〃<type 'list'>需要遍历取出每一个file
        resu_name = request.POST['name']
        resu_six = request.POST['sex']
        resu_age = request.POST['age']
        resu_experence = request.POST['experience']
        resu_position = request.POST['position']
        resu_phone = request.POST['phone']
        resu_mail = request.POST['mail']
        resu_edu = request.POST['edu']
        resu_id = request.POST['ID']
        if resu_id:
            resu_id = resu_id.replace(' ','')
        
        #------------------获取表单信息-----------------------
        
        #--------------------------------处理表单数据---------------------------------------
        if not files:
            errors.append('请选择要上传的文件')
        if not resu_phone:
            errors.append('请填写电话')
        if not resu_mail:
            errors.append('请填写邮箱')
        if errors:
            return render(request, 'import_resume2.html',{'user':user,'recruiters':recruiters,'errors':errors,'refresh':refresh})  
        for f in files:          
            if resu_mail:
                select_resume  =  Resume.objects.filter(CandidateEmail=resu_mail.encode('utf8'))
            if not select_resume and resu_phone:
                    select_resume  =  Resume.objects.filter(CandidatePhone=resu_phone.encode('utf8'))
            for chunk in f.chunks():
                if  len(select_resume)>0:                             
                    for ss in select_resume:
                        if ss.UserID==None:
                            addr_split = ss.Addr.split(separator)
                            ss.UserID=user_obj
                            ss.referrerID=user
                            ss.CandidatePhone = resu_phone
                            ss.CandidateEmail = resu_mail
                            ss.Time = timezone.now()
                            ss.save()
                            new_resume = open(os.path.join(settings.MEDIA_ROOT,'downloads' , addr_split[-1].encode('UTF-8')),'w')
                            chunk = chunk.replace('gb2312','utf-8')
                            if f.name.find('.htm') == -1:
                                new_resume.write(chunk)
                            else:
                                try:
                                    new_resume.write(chunk.decode('gb2312').encode('UTF-8'))
                                except:
                                    new_resume.write(chunk)
                                finally:
                                    pass
                            new_resume.close()    
                        else:
                            filename='<br>'.join([filename,f.name,"简历已存在于库中"])
                            #已存在，被锁定，则记录失败信息
                            Repeat_Resume.objects.get_or_create( 
                                    user_name =  user.username,
                                    resume_phone = resu_phone.encode('utf8'),
                                      )   
                else:
                    resu_experence = work_experience_switch(resu_experence) 
                    new_resume = open(os.path.join(settings.MEDIA_ROOT,'uploads',f.name.encode('UTF-8').replace(' ','-')) ,'w') 
                    if f.name.find('.htm') == -1:
                        new_resume.write(chunk)
                    else:
                        try:
                            new_resume.write(chunk.decode('gb2312','ignore').encode('UTF-8','ignore'))
                        except:
                            new_resume.write(chunk)
                        finally:
                            pass
                    new_resume.close()
                    resu_addr = os.path.join('media','uploads',f.name.encode("UTF-8").replace(' ','-'))                  
                    Resume.objects.get_or_create( 
                                                 SearchID = resu_id,
                                                 CandidateName=resu_name.encode('utf8'), 
                                                 CandidateSex=resu_six.encode('utf8'),
                                                 CandidateAge=resu_age.encode('utf8'),
                                                 CandidatePhone=resu_phone.encode('utf8'),
                                                 CandidateEmail=resu_mail.encode('utf8'),
                                                 CandidateProfile=resu_experence,
                                                 Candidate_edu=resu_edu.encode('utf8'),
                                                 PositionName=resu_position.encode('utf8'),
                                                 Addr=''.join([separator,resu_addr.encode('utf8')]),
                                                 UserID=user_obj,
                                                 referrerID= user,
                                                )  
                    if  resu_id:

                        resume_objs = import_ID.objects.filter(resume_id=resu_id)
                        if resume_objs:
                            for resume in resume_objs:
                                ISOTIMEFORMAT='%Y-%m-%d %X'
                                now_time = time.strftime( ISOTIMEFORMAT, time.localtime() )
                                if resume.Status==0 :
                                    if user_obj.id == resume.referrerID.id:
                                        resume.Status=1
                                        resume.UploaderID = user
                                        resume.remark='用户'+user.username+'于'+now_time+'上传，指定用户'+user_obj.username+'锁定'
                                        resume.save()
                                    else:
                                        resume.Status=2
                                        resume.UploaderID = user
                                        resume.remark='用户'+user.username+'于'+now_time+'上传，指定用户'+user_obj.username+'锁定'
                                        resume.save()
                                else:
                                    errors.append('此ID已由用户'+user.username+'于'+now_time+'上传，指定用户'+user_obj.username+'锁定')
                                    
        if filename=='' and len(errors) == 0:
            refresh.append('ok')
            return render(request, 'import_resume2.html',{'user':user,'recruiters':recruiters,'errors':errors,'refresh':refresh})
        else:
            errors.append('上传失败!'+filename)
            return render(request, 'import_resume2.html',{'user':user,'recruiters':recruiters,'errors':errors,'refresh':refresh})
        #--------------------------------处理表单数据---------------------------------------
          
    else:
          
        return render(request, 'import_resume2.html',{'user':user,'recruiters':recruiters})
def age_switch(age):
    '''按需求，将简历中的出生年月拿到，计算出当前多少岁
    Args:
        age:出生年月，字符串。列如：1990年1月1日
    '''
    ISOTIMEFORMAT='%Y-%m-%d %X'
    now_time = time.strftime( ISOTIMEFORMAT, time.localtime() )
    now_year = now_time.split('-')
    if len(now_year)>1:
        now_year = int(now_year[0])
    else:
        return ''
    age_year = age.split('.')
    if len(age_year)>1:
        age_year = int(age_year[0])
    else:
        return ''
    return str(now_year - age_year) + '岁'

def save_data(separator):
    '''保存数据到数据库，调用此函数的数据来源是邮件'''
    global resume_info
    global Subject
    #------------------以下对age,work_experience的变现形式修改，修改于2015.11.5----------------------
    resume_info['age'] = age_switch(resume_info['age'])
    resume_info['work_experience'] = work_experience_switch(resume_info['work_experience'])
    
    #--------------------------------------------------------------------------------------------------   

    Resume.objects.get_or_create( 
                                     CandidateName=resume_info['name'].encode('utf8'), 
                                     CandidateSex=resume_info['sex'].encode('utf8'),
                                     CandidateAge=resume_info['age'].encode('utf8'),
                                     CandidatePhone=resume_info['phone'].encode('utf8'),
                                     CandidateEmail=resume_info['E-mail'].encode('utf8'),
                                     CandidateProfile=resume_info['work_experience'],
                                     Candidate_edu=resume_info['education'].encode('utf8'),
                                     PositionName=Subject[2].encode('utf8'),
                                     Addr=''.join([separator,resume_info['path'].encode('utf8')]),
                                     SearchID=resume_info['id'].encode('utf8'),
                                    
                                    )


#上传失败的简历的处理函数
@login_required    
def repeat(request):
    '''查看导入失败，且原因为与系统中的简历重复的简历'''
    inters = []
    #cookie
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user = UserModel.objects.get(id = user_id)
    #数据
    fail_user_id = Repeat_Resume.objects.filter(user_name=user.username)
    for s in fail_user_id: 
        inter = Resume.objects.filter(CandidatePhone=s.resume_phone)
        inters.append([inter,s])
    #分页
    paginator=Paginator(inters,10)
    page_num=request.GET.get('page')
    try:
        positions=paginator.page(page_num)
    except PageNotAnInteger:
        positions=paginator.page(1)
    except EmptyPage:
        positions=paginator.page(paginator.num_pages)
    #分页〉
    t = loader.get_template("repeat.html")
    c = Context({'inters':inters})
    return HttpResponse(t.render(c))
def fail_importid(request):
    '''馋看导入失败的简历ID'''
    inters = []
    #cookie
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user = UserModel.objects.get(id = user_id)
    #数据
    fail_user_id = fail_import_id.objects.filter(referrerID=user)
    for inter in fail_user_id: 
        inters.append(inter)
      
    #分页
    paginator=Paginator(inters,10)
    page_num=request.GET.get('page')
    try:
        positions=paginator.page(page_num)
    except PageNotAnInteger:
        positions=paginator.page(1)
    except EmptyPage:
        positions=paginator.page(paginator.num_pages)
    #分页
    t = loader.get_template("fail_importid.html")
    c = Context({'inters':inters})
    return HttpResponse(t.render(c))
@login_required  
def check_idgroup(request):
    '''馋看需要下载的简历ID'''
    #cookie
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user = UserModel.objects.get(id = user_id)
    #检查需要下载的简历中，有没有系统中已存在的，返回值为需要下载的ID，这里不需要返回值
    chack_id()
    #列出状态为未处理的所有ID组
    idgroups = check_group(user)
    #分页
    paginator=Paginator(idgroups,10)
    page_num=request.GET.get('page')
    try:
        positions=paginator.page(page_num)
    except PageNotAnInteger:
        positions=paginator.page(1)
    except EmptyPage:
        positions=paginator.page(paginator.num_pages)
    #分页

    t = loader.get_template("check_idgroup.html")
    c = Context({'idgroups':idgroups})
    return HttpResponse(t.render(c))

def check_importid(request):
    '''馋看需要下载的简历ID'''
    inters = chack_id()
    #分页
    paginator=Paginator(inters,10)
    page_num=request.GET.get('page')
    try:
        positions=paginator.page(page_num)
    except PageNotAnInteger:
        positions=paginator.page(1)
    except EmptyPage:
        positions=paginator.page(paginator.num_pages)
    #分页

    t = loader.get_template("check_importid.html")
    c = Context({'inters':inters})
    return HttpResponse(t.render(c))
def filter_id_from_importID(sid,idsource,uname,fail_str,succeed_id_list,referrer_id,select_obj):
    '''判断用户上传的简历ID是否合法，有效
    Args:
        sid:上传的ID字符串，可能包含多个ID，需判断是否有效
        idsource:ID的来源
        uname:处理人的姓名
        fail_str:导入失败的ID,失败原因组陈搞得字符串
        succeed_id_list:导入成功的ID列表
        referrer_id:上传者的ID
    Returns:
        return(fail_str)---导入失败
        return('上传成功')---导入成功
    Raises:None
    '''
    list_id=sid.split("\r\n")
    for sid in list_id:
        sid=sid.strip()
        ID_index = sid.find("ID:")
        if ID_index!=-1:
            sid = sid[ID_index+len("ID:"):]
        if not (len(sid)==23 or len(sid)==8 or len(sid)==9):
            fail_str +=   'id:' + sid + '  (来自:' + idsource + ',ID长度不对' +')<br><br>'
            continue
        select_id = Resume.objects.filter(SearchID=sid)
        for ss in select_id:
            if ss.UserID==None:
                ss.UserID=uname
                ss.referrerID=referrer_id
                ss.save()
                import_ID.objects.get_or_create( 
                        user_name =  uname.username.encode('UTF-8'),
                        resume_id = sid.encode('utf8'),
                        source = idsource.encode('utf8'),
                        referrerID = referrer_id,
                        groupid = select_obj,
                        Status = 1,
                        remark = '本简历已存在于系统中，且无人锁定，系统已自动帮您锁定',
                          )                      
                succeed_id_list.append(sid)
                
            else:
                fail_str +=   'id:' + sid + '  (来自:' + idsource + ',该ID已存在于库中并被人锁定' +')<br><br>' 
                continue
        if fail_str or sid in succeed_id_list:
            continue
        id_from_importid=import_ID.objects.filter(resume_id=sid.encode('utf8'))
        if len(id_from_importid)>0 and len(sid)!=0 :
            #判定之歌ID是否已经被别人上传
            fail_import_id.objects.get_or_create( 
                user_name =  uname.username.encode('UTF-8'),
                resume_id = sid.encode('utf8'),
                source = idsource.encode('utf8'),
                referrerID = referrer_id,
                
                  )
            fail_str +=   'id:' + sid + '  (来自:' + idsource + ',该ID已被其他人定为下载目标' +')<br><br>'             
        else:
            if len(sid)!=0:              
                import_ID.objects.get_or_create( 
                        user_name =  uname.username.encode('UTF-8'),
                        resume_id = sid.encode('utf8'),
                        source = idsource.encode('utf8'),
                        referrerID = referrer_id,
                        groupid = select_obj,
                          )                      
                succeed_id_list.append(sid)
                    
    return  [fail_str,succeed_id_list]
@login_required  
def import_ResumeID(request):
    '''用户导入简历ID
       list_depart_pos:2维列表，每个元素都是【部门ID，职位ID，职位名称】的列表，转为Json个时候传到前端使用 
       errors:判断输入是否有错
       refresh:判断是否刷新父页面
    '''
 
    #cookie
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user_obj = UserModel.objects.get(id = user_id)
    ISOTIMEFORMAT='%Y-%m-%d %X'
    now_time =  time.strftime( ISOTIMEFORMAT, time.localtime() )
    recruiter_roleID=Power.objects.filter(name="简历筛选权")   
    all_recruiters =   Cor_user_Power.objects.filter(PowerID=recruiter_roleID).exclude(UserID__is_active = 0) 
    recruiters = []
    departs = get_depart(user_obj)
    '''当前用户的user_dep_list,有赛选权用户的recruiter_dep_list,'''

    for depart in departs:
        for recruiter_with_dep in all_recruiters:
            recruiter_departs = get_depart(recruiter_with_dep.UserID)
            if find_depart(depart,recruiter_departs):
                if recruiter_with_dep not in recruiters:
                    recruiters.append(recruiter_with_dep)

    list_depart_pos = []
    errors = []
    refresh = []
    for depart in departs:
        depart_poses1 =  Position.objects.filter(SecondDepartment=depart).filter(Filing=0)
        for pos in depart_poses1: 
            list_depart_pos.append([depart.id,pos.id,pos.PositionName])
        depart_poses2 =  Position.objects.filter(Depart=depart).filter(Filing=0)
        for pos in depart_poses2:               
            list_depart_pos.append([depart.id,pos.id,pos.PositionName])
    if request.method == "POST":
        user=""
        str_id=''
        zl_id_list=[]
        job_id_list=[]
        recruiter_id=""
        select_obj = None
        recruiter_obj = None
        #------------------获取页面表单信息-----------------------
        
        recruiter_id = request.POST['recruiter1']
        if recruiter_id == '':
            errors.append('简历处理人无效!')
        elif int(recruiter_id)==1:
            recruiter_obj=user_obj
        else:
            recruiter_id = request.POST['recruiter']
            if recruiter_id == '0':
                errors.append('简历处理人无效!')
            else:
                recruiter_obj = MyUser.objects.get(id=int(recruiter_id))#朝找resu_name的对象
        if   recruiter_obj :    
                user = MyUser.objects.get(username=recruiter_obj.username)#按username查询数据库，返回查询对象   
        
        depart_id = request.POST['depart'] 
        if depart_id == '0':
            errors.append('请选择您的部门')
        else:
            get_department=Department.objects.get( id = int(depart_id))
            pos_id = request.POST['pos'] 
            if pos_id == '0': 
                errors.append('请选择您需要的的招聘岗位')
            else:
                get_Position = Position.objects.get(id = int(pos_id))               
                get_remark = request.POST['remark'] 
                if not errors:
                    select_obj= importid_group.objects.create(
                                                                userID=user,
                                                                remark = get_remark,
                                                                DepartID = get_department,
                                                                PositionID = get_Position,
                                                                referrerID = user_obj,
                                                                )
        if errors:
            return render(request,'import_resume_id.html',
                      {'date':now_time,'recruiters':recruiters,'user':user_obj,'departs':departs,'poses':json.dumps(list_depart_pos),'errors':errors})
        zhilian_id = request.POST['zhilian_id']
        job51_id = request.POST['51_id']
        #------------------获取页面表单信息-----------------------
        if len(zhilian_id)>0:
            fail_and_seccess = filter_id_from_importID(zhilian_id,'智联',recruiter_obj,str_id,zl_id_list,user_obj,select_obj)
            str_id += fail_and_seccess[0]
            zl_id_list = fail_and_seccess[1]
        if len(job51_id)>0:   
            fail_and_seccess = filter_id_from_importID(job51_id,"51",recruiter_obj,str_id,job_id_list,user_obj,select_obj)
            str_id += fail_and_seccess[0]
            job_id_list = fail_and_seccess[1]
        if str_id=='':
            if len(job_id_list) or len(zl_id_list):
                sentmail(zl_id_list,job_id_list,recruiter_obj.username)
            refresh.append('ok')
        else:
            errors.append('对不起，以下ID无效，ID号后附有原因<br>'+str_id)
        return render(request,'import_resume_id.html',
                      {'date':now_time,'recruiters':recruiters,'user':user_obj,'departs':departs,'poses':json.dumps(list_depart_pos),
                       'refresh':refresh,'errors':errors})
    else:
        
        return render(request,'import_resume_id.html',
                      {'date':now_time,'recruiters':recruiters,'user':user_obj,'departs':departs,'poses':json.dumps(list_depart_pos),'errors':errors})
@login_required 
def import_resume(request):
    '''这是导入简历的接口.
    Args:
        request:http请求的request
    Returns:
        return('upload ok!')---导入成功
        return('对不起，您导入的不是智联(或51job)的html格式的简历')---导入失败
    Raises:
        DataError:Data too long for column 'Addr' at row 1"
        (If the file name is too long, an error when written to the database.)
    '''
    errors = []
    refresh = []
    select_id=''
    #cookie
    UserModel = get_user_model()
    session_id = request.COOKIES['sessionid']
    user_id = Session.objects.get(session_key=session_id).get_decoded().get('_auth_user_id')
    user_obj = UserModel.objects.get(id = user_id)
    now_time = time.time() 
    all_user = MyUser.objects.all()
    recruiter_roleID=Power.objects.filter(name="简历筛选权")   
    recruiters =   Cor_user_Power.objects.filter(PowerID=recruiter_roleID).exclude(UserID__is_active = 0) 
    if request.method == "POST":
        user=""
        filename=''
        
        referrer_user = None
        #------------------获取页面表单信息-----------------------
        referrer_user_name = request.POST['referrer']
        referrer_users = MyUser.objects.filter(username=referrer_user_name)
        for referrer_user in referrer_users:
            pass
        if not referrer_user:
            errors.append('无效的推荐人')
            return render(request,'import_resume.html',{'date':now_time,'recruiters':recruiters,'user':user_obj,'all_user':all_user,'errors':errors})
        uname = request.POST['recruiter']
        s = MyUser.objects.filter(username=uname.encode('UTF-8'))#按username查询数据库，返回查询对象
        for user in s:
            pass
        if user == '' :
            errors.append('无效的简历归属人')
            return render(request,'import_resume.html',{'date':now_time,'recruiters':recruiters,'user':user_obj,'all_user':all_user,'errors':errors})    
        files = request.FILES.getlist('headImg')#FILES是上传文件的列表<type 'list'>，需要用getlist方法取得里面的元素
        refresh.append('ok')
        #------------------获取页面表单信息-----------------------
        
        #--------------------------------处理表单信息---------------------------------------
        for f in files:
            created_obj = None
            if f.name.find('51job')!=-1 and f.name.find('.htm')!=-1:   #对文件名进行检查，确认是不是51（智联）的简历  
                
                for chunk in f.chunks():              
                    mutex = threading.Lock()
                    mutex.acquire()
                    try:       
                        dict_info=parser_with_51( chunk)
                    finally:
                        mutex.release()
                    
                    if dict_info['id']=='':
                        filename='<br>'.join([filename,f.name+'（简历不符合要求）']) 
                        continue   
                    chunk = chunk.replace('gb2312','utf-8') 
                    if dict_info['E-mail']:
                        select_id  =  Resume.objects.filter(CandidateEmail=dict_info['E-mail'].encode('utf8'))
                    if not select_id :
                        if dict_info['phone']:
                            select_id  =  Resume.objects.filter(CandidatePhone=dict_info['phone'].encode('utf8'))
                    if len(select_id)>0 : #鎴愬姛杩斿洖鏌ヨ瀵硅薄閭ｄ箞瑙嗕负搴撻噷宸茬粡淇濆瓨杩囪绠�鍘嗕簡
                        
                        for ss in select_id:
                            if ss.UserID==None:
                                ss.UserID=user
                                ss.referrerID=referrer_user
                                ss.Time = timezone.now()
                                ss.save()
                                new_resume = open("/home/resume/project"+ss.Addr.encode('UTF-8'),'w')
                                new_resume.write(chunk.decode('gb2312','ignore').encode('UTF-8','ignore'))
                                new_resume.close()    
                            else:
                                filename='<br>'.join([filename,f.name])
                                #成功返回查询对象那么视为库里已经保存过该简历了
                                send_back(dict_info,user_obj)
                                Repeat_Resume.objects.get_or_create( 
                                        user_name =  referrer_user.username,
                                        resume_phone = dict_info['phone'].encode('utf8'),
                                          )   
                    else:
                        destination = open(os.path.join(settings.MEDIA_ROOT,'uploads',f.name.encode('UTF-8')) ,'w')
                        destination.write(chunk.decode('gb2312','ignore').encode('UTF-8','ignore'))
                        dict_info['work_experience']= int(work_experience_switch(dict_info['work_experience']))
                        created_obj ,created= Resume.objects.get_or_create( 
                                SearchID= dict_info['id'],                 
                                CandidateName=dict_info['name'].encode('utf8'), 
                                CandidateSex=dict_info['sex'].encode('utf8'),
                                CandidateAge=dict_info['age'].encode('utf8'),
                                CandidatePhone=dict_info['phone'].encode('utf8'),
                                CandidateEmail=dict_info['E-mail'].encode('utf8'),
                                CandidateProfile=dict_info['work_experience'],
                                Addr=r'/media/uploads/' + f.name.encode('UTF-8','ignore'),
                                UserID=user,
                                referrerID= referrer_user,
                               )  
                         
                        destination.close()
            elif  f.name.find('智联')!=-1 and f.name.find('.htm')!=-1:
                
                for chunk in f.chunks():              
                    mutex = threading.Lock()
                    mutex.acquire()
                    try:       
                        dict_info=parser_with_zhilian( chunk.decode('UTF-8'))
                    finally:
                        mutex.release()
                    chunk = chunk.replace('gb2312','utf-8')
                    if dict_info['E-mail']:
                        select_id  =  Resume.objects.filter(CandidateEmail=dict_info['E-mail'].encode('utf8'))
                    if not select_id :
                        if dict_info['phone']:
                            select_id  =  Resume.objects.filter(CandidatePhone=dict_info['phone'].encode('utf8'))
                    '''
                    return HttpResponse('phone:'+str(len(dict_info['phone']))+dict_info['phone']+'<br>'
                                 'mail:'+str(len(dict_info['E-mail']))+dict_info['E-mail']+'<br>'
                                 'select_id:'+str(len(select_id)))
                    '''
                    if dict_info['id']=='':
                        filename='<br>'.join([filename,f.name+'（简历不符合要求）'])
                        continue                                           
                    if len(select_id)>0 :#成功返回查询对象那么视为库里已经保存过该简历了
                        for ss in select_id:
                            if ss.UserID_id==None:
                                ss.UserID=user
                                ss.referrerID=referrer_user
                                ss.Time = timezone.now()
                                ss.save()
                                new_resume = open("/home/resume/project"+ss.Addr.encode('UTF-8'),'w')
                                new_resume.write(chunk)
                                new_resume.close()
                            else:
                                filename='<br>'.join([filename,f.name])
                                #保存上传失败的简历的信息 
                                send_back(dict_info,user_obj)
                                Repeat_Resume.objects.get_or_create( 
                                        user_name = referrer_user.username,
                                        resume_phone = dict_info['phone'].encode('utf8'),
                                         )        
                    else:
                        destination = open(os.path.join(settings.MEDIA_ROOT,'uploads',f.name.encode('UTF-8')),'w')
                        destination.write(chunk)
                        dict_info['work_experience']= int(work_experience_switch(dict_info['work_experience']))
                        created_obj ,created = Resume.objects.get_or_create(
                                SearchID= dict_info['id'],                  
                                CandidateName=dict_info['name'].encode('utf8'), 
                                CandidateSex=dict_info['sex'].encode('utf8'),
                                CandidateAge=dict_info['age'].encode('utf8'),
                                CandidatePhone=dict_info['phone'].encode('utf8'),
                                CandidateEmail=dict_info['E-mail'].encode('utf8'),
                                CandidateProfile=dict_info['work_experience'],
                                Addr=r'/media/uploads/' + f.name.encode('utf8'),
                                UserID=user,
                                referrerID= referrer_user,
                                
                               ) 
                          
                        destination.close()
        #--------------------------------处理表单信息---------------------------------------
            else:
                errors.append('对不起，您导入的不是智联(或51job)的html格式的简历')
                return render(request,'import_resume.html',{'date':now_time,'recruiters':recruiters,'user':user_obj,'all_user':all_user,'errors':errors})
            if created_obj:
                ISOTIMEFORMAT='%Y-%m-%d %X'
                now_time = time.strftime( ISOTIMEFORMAT, time.localtime() )
                id_objs = import_ID.objects.filter(resume_id = created_obj.SearchID)
                
                for id_obj in id_objs:
                    id_obj.Status=1
                    id_obj.UploaderID = user_obj
                    id_obj.remark='用户'+user_obj.username+'于'+now_time+'上传，指定用户'+user.username+'锁定'
                    id_obj.save()
        if filename=='':
            
            return render(request,'import_resume.html',{'date':now_time,'recruiters':recruiters,'user':user_obj,'all_user':all_user,'errors':errors
                                                        ,'refresh':refresh})
        else:
            errors.append('以下文件导入失败，原因：已存在于库中。 您可以在简历管理->导入失败的简历中查看!<br>'+filename)
            return render(request,'import_resume.html',{'date':now_time,'recruiters':recruiters,'user':user_obj,'all_user':all_user,'errors':errors,
                                                        'refresh':refresh})
    else:  
        return render(request,'import_resume.html',{'date':now_time,'recruiters':recruiters,'user':user_obj,'all_user':all_user,'errors':errors,
                                                    'refresh':refresh})
class ShowStructure_new_zhilian(sgmllib.SGMLParser):
    ''' 解析html的类,继承自sgmllib.SGMLParser.
    
    instructions:解析来自智联的简历，使用SGMLLIB模块
    
    Attributes: 
        span:表示遇到<span></span>
        tr:表示遇到<tr></tr>
        td:表示遇到<td></td>
        font:表示遇到<front><front>
        p:表示遇到<p></p>
    
    Returns:
        NO return---数据在函数中处理好放入全局变量   global txt
                                        global info_list
                                        global resume_info
                                        global Subject
                                        global Date
    Raises:
        not found
    
    '''    
    span=''
    tr=''
    td=''
    font=''
    p=''
    count=0
    def start_span(self,attrs):
        style=[v for k, v in attrs if k=='style']
        if style==["display:none;"]:
            self.span=1
        if style==["display:block;padding:0 0 0 7px;margin:0;font-family:Arial;font-size:12px;color:#fff;"]:
            self.span=2
    def start_tr(self,attrs):
        style=[v for k, v in attrs if k=='style']
        width=[v for k, v in attrs if k=="width"]
        height=[v for k, v in attrs if k=="height"]
        if style==["height:30px"] and width==["466"]:
            self.tr=1
        if height==["54"]:
            self.tr=2
    def end_tr(self):
        if self.tr!='':
            self.tr=''
    def start_td(self,attrs):
        width=[v for k, v in attrs if k=="width"]
        style=[v for k, v in attrs if k=="style"]
        height=[v for k, v in attrs if k=="height"]
        if style==["font-size:12px;color:#000000;line-height:24px;padding-left:12px;word-break: break-all; word-wrap:break-word;"] and width==["466"]:
            self.td=1
        if width==["210"] and height==["54"] and style==["background:#2f9ddf;border-radius:4px;word-break: break-all; word-wrap:break-word;padding-left:5px;padding-bottom:5px;"]:
            self.td=2
    def end_td(self):
        if self.td!='':
            self.td=''
    def start_p(self,attrs):
        style=[v for k, v in attrs if k=="style"]
        if  style==["font-size:22px;color:#fff;font-weight:bold;line-height:35px;padding:0;margin:0;padding-left:7px;font-family:Arial;"]:
            self.p=2
    def end_p(self):
        if self.p!='':
            self.p=''
    def start_font(self,attrs):
        style=[v for k, v in attrs if k=="style"]
        if  style==["font-weight:bold"]:
            self.font=1
    def end_font(self):
        if self.font!='':
            self.font=''
    def end_span(self):
        if self.span!='':
            self.span=''
    def handle_data(self, data):
        if self.span==1:
            m = re.match(r'^[\s\S]*?ID:([\s\S]*?)$',data)
            if m!=None:
                resume_info['id']=m.group(1)
        if self.tr==1 and self.td==1 and self.font==1:
            self.count=self.count+1
            print 'sex:',data.encode('UTF-8')
            if self.count==1:
                m = re.match(r'^[\s\S]*?([0-9]+)[\s\S]*?([0-9]+)[\s\S]*?$',data)
                if m==None:
                    resume_info['sex']=data.encode('UTF-8')
                else:
                    resume_info['age']=data.encode('UTF-8') 
            if self.count==2:
                m = re.match(r'^[\s\S]*?([0-9]+)[\s\S]*?([0-9]+)[\s\S]*?$',data)
                if m==None:
                    resume_info['work_experience']=data.encode('UTF-8')
                else:
                    resume_info['age']=data.encode('UTF-8') 
            if self.count==3:
                resume_info['age']=data.encode('UTF-8')
        if self.tr==2 and self.td==2 and self.p==2:
            resume_info['phone']=data.encode('UTF-8')
        if self.tr==2 and self.td==2 and self.span==2:
            resume_info['E-mail']=data.encode('UTF-8')    
class ShowStructure(sgmllib.SGMLParser):
    ''' 解析html的类,继承自sgmllib.SGMLParser.
    
    instructions:解析来自51的简历，使用SGMLLIB模块
    
    Attributes: count :    计数，记录一个特定属性的<td>出现的次数这里只要第1次的数据
                job_id_is:    51job的简历的ID的<p>
                job_phone_is:    51job的简历的phone的<td>
                job_addr_is:   51job的简历的addr的<td> 
                job_mail:    51job的简历的e-mail的<a>
                job_tojob:    51job的简历的求职意向的<td>
                job_span_is:    51job的简历的<span>
    
    Returns:
        NO return---数据在函数中处理好放入全局变量   global txt
                                        global info_list
                                        global resume_info
                                        global Subject
                                        global Date
    Raises:
        not found
    
    '''
    
    job_id_is=''
    job_phone_is=''
    job_addr_is=''
    job_mail=''
    job_span_is=''
    def start_td(self,attrs):      
   
        height = [v for k, v in attrs if k=='height']
        colspan =   [v for k, v in attrs if k=='colspan']         
        width =[v for k, v in attrs if k=='width']
        if height == ['20'] and colspan ==["3"] :
            self.job_phone_is =1

        if height==["20"] and width ==["42%"]:
            self.job_addr_is = 1
            
    def end_td(self):
        if self.job_phone_is==1:
            self.job_phone_is=''
        if self.job_addr_is==1:
            self.job_addr_is=''
            
    def start_p(self,attrs):
        print attrs
        if attrs==[]:
            self.job_id_is = 1
    def end_p(self):
        if self.job_id_is == 1:
            self.job_id_is = ''
    def start_a(self,attrs):
        class_in_a = [v for k, v in attrs if k=='class']
        if class_in_a ==['blue1']:
            self.job_mail = 1
    def end_a(self):
        if self.job_mail==1:
            self.job_mail=''
    def start_span(self,attrs):
        class_in_span = [v for k, v in attrs if k=='class']
        if class_in_span == ['blue1'] :
            self.job_span_is=1
    def end_span(self):
        if self.job_span_is == 1:
            self.job_span_is = ''

    def handle_data(self, data):
        global txt
        global tagstack
        global info_list
        global resume_info
        global Subject
        global Date
        if self.job_span_is==1:
            info_list.append(data)
        if self.job_id_is == 1 :
            m = re.match(r'^[\s\S]*?\(ID:([\s\S]*?)\)',data)
            if m != None:
                resume_info['id']=m.group(1)
        if self.job_mail == 1:
            m = re.match(r'^[\s\S]*?([0-9a-zA-Z]+\@[\s\S]*)$',data)
            if m == None:
                pass
            else:
                resume_info['E-mail']= m.group(1)
        if self.job_phone_is == 1:
            m = re.match(r'^[\s\S]*?([0-9]{11})[\s\S]*$',data)
            if m != None:
                resume_info['phone']=m.group(1)
        if self.job_addr_is == 1:
            pass

def guess_charset(msg):
    '''检查文本的编码'''
    charset = msg.get_charset()
    if charset is None:
        content_type = msg.get('Content-Type', '').lower()
        pos = content_type.find('charset=')
        if pos >= 0:
            charset = content_type[pos + 8:].strip()
    return charset

def decode_str(s):
    '''解码字符串'''
    value, charset = decode_header(s)[0]
    if charset:
        value = value.decode(charset, 'ignore')
    return value

def print_info(msg, indent=0):
    global txt
    global tagstack
    global resume_info
    global Subject
    global Date
    global info_list
    if indent == 0:
    # 邮件的From, To, Subject存在于根对象上:
        for header in ['From', 'To', 'Subject','Date']:
            value = msg.get(header, '')
            if value:
                if header == 'Date':
                    m = re.match(r'^[\s\S]*?([0-9]+)\s+(\w+)\s+([0-9]+)\s+([0-9]+):([0-9]+):([0-9]+)[\s\S]*$',value)
                    month = m.group(2)
                    #在这里对时间进行了转换，方便进行比较
                    if month == 'Jan':
                        month =1
                    elif month == 'Feb':
                        month =2
                    elif month == 'Mar':
                        month =3
                    elif month == 'Apr':
                        month =4
                    elif month == 'May':
                        month =5
                    elif month == 'Jun':
                        month =6
                    elif month == 'Jul':
                        month =7
                    elif month == 'Aug':
                        month = 8
                    elif month == 'Sep':
                        month =9
                    elif month == 'Oct':
                        month =10
                    elif month == 'Nov':
                        month =11
                    elif month == 'Dec':
                        month =12
                    str_month = str(month)
                    str_day = m.group(1)
                    if len(str_month)<2:
                        str_month = ''.join(['0',str_month])
                    if len(m.group(1))<2:
                        str_day = ''.join(['0',m.group(1)])
                    Date.append(''.join([m.group(3),str_month,str_day,m.group(4),m.group(5),m.group(6)]))                   
                elif header=='Subject':
                    # 需要解码Subject字符串:
                    value = decode_str(value)
                    Subject.append(value)
                    m = re.match(r'^.*?(Zhaopin\.com)\)([\s\S]*)-[\s\S]*$|^\((51job\.com)\)[\s\S]*?$',Subject[0])
                    if m==None or m.group(1)==None:
                        m = re.match(r'^.*?(51job\.com)\)([\s\S]*)$',Subject[0])
                        if m != None:
                            Subject.append(m.group(1))
                            s=m.group(2).encode('UTF-8').split('－')
                            n = re.match(r'^[\s\S]{5}([\s\S]*)$',s[0].decode('UTF-8'))
                            if n !=None:
                                Subject.append(n.group(1))
                            else:
                                Subject.append(m.group(2))
                    else:  
                        Subject.append(m.group(1))
                        n = re.match(r'^[\s\S]{4}([\s\S]*)$',m.group(2))                       
                        if n != None:
                            Subject.append(n.group(1))
                        else:
                            Subject.append(m.group(2))
#                         print 'work:',Subject[2]
                else:
                    # 需要解码Email地址:
                    hdr, addr = parseaddr(value)
                    name = decode_str(hdr)
                    value = u'%s <%s>' % (name, addr) 
                    if header == 'From':
                        From = []
                        From.append(value)
                        m = re.match(r'^[\s\S]*?\s+([\s\S]*?)<[\s\S]*$',From[0])
                        resume_info['name'] = m.group(1)
                                        
#             print('%s%s:%s' % ('  ' * indent, header, value))        
    if (msg.is_multipart()):
  
#         如果邮件对象是一个MIMEMultipart,
#         get_payload()返回list，包含所有的子对象:
        parts = msg.get_payload()
        for n, part in enumerate(parts):
#             print('%spart %s' % ('  ' * indent, n))
#             print('%s--------------------' % ('  ' * indent))
            # 递归打印每一个子对象:
            print_info(part, indent + 1)
    else:
        # 邮件对象不是一个MIMEMultipart,
        # 就根据content_type判断:
        content_type = msg.get_content_type()
        if content_type=='text/plain' or content_type=='text/html':
            # 纯文本或HTML内容:
            content = msg.get_payload(decode=True)
            # 要检测文本编码:
            charset = guess_charset(msg)
            if charset:
                content = content.decode(charset, 'ignore')
                content=content.replace('gb2312','utf-8')
                txt.append(content)
                
#             print('%sText: %s' % ('  ' * indent, content ))
            
        else:
            pass
            # 不是文本,作为附件处理:
#            print('%sAttachment: %s' % ('  ' * indent, content_type))

def parser_info_from_zhilian():
    global txt
    global tagstack
    global resume_info
    global Subject
    global Date
    global info_list 
    #----------------------------------------------解析html文本-------------------------------------------
    for info_list_number in range(len(info_list)):
        if info_list_number == 0:   #info_list_number为info_list的下表，由于简历的某一项文本格式和文本长度都不一定，所以这里进行了多次判断
            #有5个‘|’分割的信息
            n=re.match(r'([\s\S]*)\|([\s\S]*)\|([\s\S]*)\|([\s\S]*)\|\s+(.*)\s+\|([\s\S]*)$|([\s\S]*)\|([\s\S]*)\|([\s\S]*)\|\s+(.*)\s+\|([\s\S]*)$',info_list[info_list_number])
            if  n == None or n.group(1)==None:
                    #有4个‘|’分割的信息
                    n=re.match(r'^([\s\S]*)\|([\s\S]*)\|([\s\S]*)\|\s+(.*)\s+\|([\s\S]*)$|([\s\S]*)\|([\s\S]*)\|([\s\S]*)\|\s+(.*)$',info_list[info_list_number])
                    if n == None or n.group(1)==None:
                        #有3个‘|’分割的信息
                        n=re.match(r'^([\s\S]*)\|([\s\S]*)\|([\s\S]*)\|\s+(.*)$',info_list[info_list_number])
                        for i in [1,2,3,4]: #去掉格式，拿到纯文本信息
                            if i == 1 and n!=None:
                                m = re.match(r'^(.*)\s+[\s\S]*$',n.group(i))
                                if m!=None:
                                    resume_info['sex'] = m.group(1)
                            elif i  == 2 and n!=None:
                                m = re.match(r'^\s+(.*?)\s+(.*)\s+$',n.group(i))
                                if m!=None:
                                    resume_info['age']=m.group(1)+m.group(2)
                            elif i == 3 and n!=None:
                                m = re.match(r'^\s+(.*)\s+$',n.group(i))
                                if m!=None:
                                    resume_info['registered_addr'] = m.group(1)
                            elif i == 4 and n!=None:
                                resume_info['now_addr'] = n.group(4)
                    else:
                        for i in [1,2,3,4,5]:   #去掉格式，拿到纯文本信息
                            if i == 1 and n!=None:
                                m = re.match(r'^(.*)\s+[\s\S]*$',n.group(i))
                                if m!=None:
                                    resume_info['sex'] = m.group(1)
                            elif i  == 2 and n!=None:
                                m = re.match(r'^\s+(.*)\s+(.*)\s+$',n.group(i))
                                if m==None:
                                    m = re.match(r'^\s+(.*)\s+$',n.group(i))
                                    if m!=None:
                                        resume_info['marital'] = m.group(1)
                                else:
                                    resume_info['age']=m.group(1)+m.group(2)
                            elif i == 3 and n!=None:
                                m = re.match(r'^\s+(.*)\s+$',n.group(i))
                                if m==None:
                                    m = re.match(r'^\s+(.*)\s+(.*)\s+$',n.group(i))
                                    if m!=None:
                                        resume_info['age']=''.join([m.group(1)+m.group(2)])
                                else:
                                    resume_info['registered_addr'] = m.group(1)
                            elif i == 4 and n!=None:
                                if resume_info['registered_addr'] == '':
                                    resume_info['registered_addr'] = n.group(4)
                                else:
                                    resume_info['now_addr'] = n.group(4)
                            elif i == 5 and n!=None:      
                                m = re.match(r'^\s+(.*)$',n.group(i))
                                if resume_info['now_addr'] == '' and  m!=None:
                                    resume_info['now_addr'] = m.group(1)
                                else:
                                    if m!=None:
                                        resume_info['education'] = m.group(1)
            else:
                for i in [1,2,3,4,5,6]:     #去掉格式，拿到纯文本信息
                    if i == 1 and n!=None:
                        m = re.match(r'^(.*)\s+[\s\S]*$',n.group(i))
                        if m!=None:
                            resume_info['sex'] = m.group(1)
                    elif i == 2 and n!=None:
                        m = re.match(r'^\s+(.*)\s+$',n.group(i))
                        if m!=None:
                            resume_info['marital'] = m.group(1)
                    elif i  == 3 and n!=None:
                        m = re.match(r'^\s+(.*)\s+(.*)\s+$',n.group(i))
                        if m!=None:
                            resume_info['age']=m.group(1)+m.group(2)
                    elif i == 4 and n!=None:
                        m = re.match(r'^\s+(.*)\s+$',n.group(i))
                        if m!=None:
                            resume_info['registered_addr'] = m.group(1)
                    elif i == 5 and n!=None:
                        resume_info['now_addr'] = n.group(5)
                    elif i == 6 and n!=None:
                        m = re.match(r'^\s+(.*)$',n.group(i))
                        if m!=None:
                            resume_info['education'] = m.group(1)
        elif info_list_number == 1:
            n=re.match(r'^\s(.*)\s+',info_list[info_list_number])
            if n!=None:
                resume_info['work_experience'] = n.group(1)
        elif info_list_number == 2:
            #print info_list[info_list_number]
            n=re.match(r'^[\s\S]*?([0-9]*)$',info_list[info_list_number])
            if n!=None:
                resume_info['phone']=n.group(1)
        elif info_list_number == 3:
            pass
        elif info_list_number == 4:
            n=re.match(r'(^[\s\S]*)',info_list[info_list_number])
            if n!=None:
                resume_info['E-mail'] = n.group(1)
    #----------------------------------------------解析html文本-------------------------------------------
     
def parser_info_from_51job():
    global txt
    global tagstack
    global resume_info
    global Subject
    global Date
    global info_list
    if len(info_list)>=2:
        resume_info['work_experience'] = info_list[1]
    if len(info_list)>=4:
        resume_info['sex'] = info_list[3]
    if len(info_list)>=6:
        b = info_list[5].split('(')        
        b = b[1].split(') ')
        m = re.match(u'^([0-9]{4})[\s\S]*?([0-9]+)[\s\S]*?([0-9]+)[\s\S]*?$',b[0])
        if m!=None:
            resume_info['age']='.'.join([m.group(1),m.group(2)])

def home(request):
    return render(request, 'home.html')

def receive_msg():
    '''这是一个接受邮件的线程，启动后就托管给后台
    
    instructions:实现接受邮件，并判断哪些邮件时新邮件，目前之就收智联和51的简历
    
    Args:
         NO args
    
    Returns:
        NO return---目前没有需要返回值的地方
    Raises:
        not found
    '''
    global txt
    global tagstack
    global resume_info
    global Subject
    global Date
    global info_list
    email = 'si_zhaopin@nantian.com.cn'
    password = 'sizhaopin123456'
    pop3_server = 'pop.263.net'   
    # 连接到POP3服务器:
    server = poplib.POP3(pop3_server)
    server.set_debuglevel(1)
    server.user(email)
    server.pass_(password)
    starter = 0
  
    # list()返回所有邮件的编号:
    resp, mails, octets = server.list()
    # 可以查看返回的列表类似['1 82923', '2 2184', ...]
    index = len(mails)
    separator = ''
    if len(settings.MEDIA_ROOT.split('\\'))>1:
        separator = '\\'
    else :
        separator = '/'
    if index > starter:
        for i in range(0,index):
            info_list = []
            resume_info={'path':'','registered_addr':'','name':'', 'sex':'', 'age':'', 'work_experience':'', 'now_addr':'', 'id':'', 'phone':'', 'E-mail':'', 'education':'','marital':''}
            Subject = []
            txt =[]
            Date = []   
            select_phone = ''         
            # lines存储了邮件的原始文本的每一行,
            # 可以获得整个邮件的原始文本:
            resp, lines, octets = server.retr(index-i)         
            msg_content = b'\r\n'.join(lines).decode('UTF-8')            
            msg = Parser().parsestr(msg_content)
            print_info(msg) # msg就是要解析的邮件生成的实例,这里是第一次分析邮件信息，根据这次的信息，决定收取哪些邮件

            with codecs.open(os.path.join(settings.MEDIA_ROOT,'downloads','Date'), 'r', 'UTF-8') as f:
                    last_time = f.read()
                    if last_time >= Date[0] or len(last_time)==0:   #根据邮件的发送时间来判断库里有没有该邮件
                        
                        if last_time >= Date[0]:     #如果有上次接受最后一封邮件的记录时间，并且>=本邮件，从编号为index的邮件开始递减定位新邮件
                            for p in range(1,i+2):
                                info_list = []
                                resume_info={'path':'','registered_addr':'','name':'', 'sex':'', 'age':'', 'work_experience':'', 'now_addr':'', 'id':'', 'phone':'', 'E-mail':'', 'education':'','marital':''}
                                Subject = []
                                txt =[]
                                Date = []  
                                if p>i:           
                                    server.quit()
                                    return 
                                resp, lines, octets = server.retr(index-i+p)                                                                      
                                msg_content = b'\r\n'.join(lines).decode('UTF-8')
                                msg = Parser().parsestr(msg_content)
                                print_info(msg)
                                if filter_education(txt[0])==-1:
                                    continue
                                ShowStructure().feed(txt[0])
                                
                                
                                
                                if Subject[0].find('Zhaopin.com')==-1 and Subject[0].find('51job.com')==-1 :
                                    continue
                                if Subject[1] == 'Zhaopin.com':
                                    txt[0]=txt[0].replace('GB2312','utf-8')
                                    ShowStructure_new_zhilian().feed(txt[0])
                                    name = os.path.join('media','downloads',resume_info['name'].encode('UTF-8').replace(' ','')+resume_info['phone'])
                                    resume_info['path']='.'.join([name,'html'])
                                    if resume_info['E-mail']:
                                        select_phone  =  Resume.objects.filter(CandidateEmail=resume_info['E-mail'].encode('utf8'))
                                    if not select_phone and resume_info['phone']:
                                        select_phone  =  Resume.objects.filter(CandidatePhone=resume_info['phone'].encode('utf8'))
                                
                                    if len(select_phone)>0 :  #成功返回查询对象那么视为库里已经保存过该简历了
                                        with codecs.open(os.path.join(settings.BASE_DIR,resume_info['path']).encode('utf8'), 'w', 'UTF-8') as f:
                                            f.write(txt[0])
                                        for s in select_phone:
                                            s.Time = timezone.now()
                                            s.save()
                                        continue
                                    
                                    n=re.match(r'^([0-9]+)[\s\S]*?([0-9]+)[\s\S]*$',resume_info['age'])
                                    if n!=None:
                                        resume_info['age']='.'.join([n.group(1),n.group(2)])
                                    with codecs.open(os.path.join(settings.BASE_DIR,resume_info['path']).encode('utf8'), 'w', 'UTF-8') as f:
                                            f.write(txt[0])
                                    
                                if Subject[1] == '51job.com':
                                    parser_info_from_51job()
                                    name = os.path.join('media','downloads',resume_info['name'].encode('UTF-8').replace(' ','')+resume_info['id'])
                                    resume_info['path']='.'.join([name,'html'])                                 
                                    if  resume_info['E-mail']:
                                        select_phone  =  Resume.objects.filter(CandidateEmail=resume_info['E-mail'].encode('utf8'))
                                    if not select_phone and resume_info['phone']:
                                        select_phone  =  Resume.objects.filter(CandidatePhone=resume_info['phone'].encode('utf8'))
                                    if len(select_phone)>0 :  #成功返回查询对象那么视为库里已经保存过该简历了
                                        with codecs.open(os.path.join(settings.BASE_DIR,resume_info['path']).encode('utf8'), 'w', 'UTF-8') as f:
                                                f.write(txt[0])
                                        for s in select_phone:
                                            s.Time = timezone.now()
                                            s.save()
                                        continue
                                    with codecs.open(os.path.join(settings.BASE_DIR,resume_info['path']).encode('utf8'), 'w', 'UTF-8') as f:
                                            f.write(txt[0])
                                with codecs.open(os.path.join(settings.MEDIA_ROOT,'downloads','Date'), 'w', 'UTF-8') as f:
                                        f.write(Date[0])
                                
                                save_data(separator)
                        if  len(last_time)==0:#第一次接受邮件，Data文件为空，从编号为1的邮件开始收取
                            for p in range(1,index+2):
                                info_list = []
                                resume_info={'path':'','registered_addr':'','name':'', 'sex':'', 'age':'', 'work_experience':'', 'now_addr':'', 'id':'', 'phone':'', 'E-mail':'', 'education':'','marital':''}
                                Subject = []
                                txt =[]
                                Date = []
                                if p>index:           
                                    server.quit()
                                    return 
                                resp, lines, octets = server.retr(p)                                                                      
                                msg_content = b'\r\n'.join(lines).decode('UTF-8')
                                msg = Parser().parsestr(msg_content)
                                print_info(msg)
                                if filter_education(txt[0])==-1:
                                    continue
                                ShowStructure().feed(txt[0])
                                
                                if Subject[0].find('Zhaopin.com')==-1 and Subject[0].find('51job.com')==-1 :
                                    continue
                                
                                if Subject[1] == 'Zhaopin.com':
                                    txt[0]=txt[0].replace('GB2312','utf-8')
                                    ShowStructure_new_zhilian().feed(txt[0])
                                    name = os.path.join('media','downloads',resume_info['name'].encode('UTF-8').replace(' ','')+resume_info['phone'])
                                    resume_info['path']='.'.join([name,'html'])
                                    if  resume_info['E-mail']:
                                        select_phone  =  Resume.objects.filter(CandidateEmail=resume_info['E-mail'].encode('utf8'))
                                    if not select_phone and  resume_info['phone']:
                                        select_phone  =  Resume.objects.filter(CandidatePhone=resume_info['phone'].encode('utf8'))
                                    if len(select_phone)>0 :  #成功返回查询对象那么视为库里已经保存过该简历了
                                        with codecs.open(os.path.join(settings.BASE_DIR,resume_info['path']).encode('utf8'), 'w', 'UTF-8') as f:
                                            f.write(txt[0])
                                        for s in select_phone:
                                            s.Time = timezone.now()
                                            s.save()
                                        continue
                                    
                                    n=re.match(r'^([0-9]+)[\s\S]*?([0-9]+)[\s\S]*$',resume_info['age'])
                                    if n!=None:
                                        resume_info['age']='.'.join([n.group(1),n.group(2)])
                                    with codecs.open(os.path.join(settings.BASE_DIR,resume_info['path']).encode('utf8'), 'w', 'UTF-8') as f:
                                            f.write(txt[0])
                                   
                                if Subject[1] == '51job.com':
                                    parser_info_from_51job()
                                    name = os.path.join('media','downloads',resume_info['name'].encode('UTF-8').replace(' ','')+resume_info['id'])
                                    resume_info['path']='.'.join([name,'html'])
                                    if  resume_info['E-mail']:
                                        select_phone  =  Resume.objects.filter(CandidateEmail=resume_info['E-mail'].encode('utf8'))
                                    if not select_phone and resume_info['phone']:
                                        select_phone  =  Resume.objects.filter(CandidatePhone=resume_info['phone'].encode('utf8'))
                                    if len(select_phone)>0 :  #成功返回查询对象那么视为库里已经保存过该简历了
                                        with codecs.open(os.path.join(settings.BASE_DIR,resume_info['path']).encode('utf8'), 'w', 'UTF-8') as f:
                                            f.write(txt[0])
                                        for s in select_phone:
                                            s.Time = timezone.now()
                                            s.save()
                                        continue
                                    with codecs.open(os.path.join(settings.BASE_DIR,resume_info['path']).encode('utf8'), 'w', 'UTF-8') as f:
                                            f.write(txt[0])
                                with codecs.open(os.path.join(settings.MEDIA_ROOT,'downloads','Date'), 'w', 'UTF-8') as f:
                                        f.write(Date[0])
                                
                                save_data(separator) 
                            
                    else:
                        continue

    else:
        server.quit()
        return 
    
def receive_middle():
    '''This is the middle of the resume function '''
    
    lock = threading.Lock()
    lock.acquire()
    try:       
        t = threading.Thread(target=receive_msg, name='receiveThread')
        t.setDaemon(True)
        t.start()
    finally:
        lock.release()
def receive(request):
    '''This is open to the public to accept resume interface, a URL''' 
    #receive_msg()
    receive_middle()
    return HttpResponse('ok')
