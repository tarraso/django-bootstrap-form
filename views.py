'''Views for using the django class base views'''
from __future__ import division
from django.views.generic import View
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from inspect import ismethod,isfunction
import json
from math import ceil
from django.core.urlresolvers import NoReverseMatch
class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)



class DeleteObjView(LoginRequiredMixin,View):
    obj_klass = None
    redirect_url = None


    def get(self, request,obj_id):
        obj = self.obj_klass.objects.get(id=obj_id)
        #Create sucess message before deleteing
        success_msg = '%s deleted' % obj


        try:
            obj.safe_delete(request.user)
            messages.success(request,success_msg)
        except Exception,e:
            print e
            messages.error(request,'Could not delete %s' % obj)

        if(self.redirect_url):
            return redirect(reverse(self.redirect_url))
        else:
            return redirect('/')


class EditObjView(LoginRequiredMixin,View):
    '''Edits an exisiting object'''
    obj_klass = None
    form_klass = None
    template = 'bootstrapform/generic_edit.html'
    ajax_template = 'bootstrapform/generic_edit_ajax.html'
    obj_name = None
    _settings_ovr = {'edit':True}
    delete_url = None
    redirect_page = None


    def get_extra_settings(self):
        '''Extra settings common to every view'''
        if(self.obj_name == None):
            self.obj_name = self.obj_klass.__name__

        return {'obj_name':self.obj_name,
                }

    def get(self, request,obj_id):
        obj = self.obj_klass.objects.get(id=obj_id)
        form = self.form_klass(instance=obj)
        settings = {'f':form}
        settings['delete_url'] = reverse(self.delete_url,kwargs={'obj_id':obj_id}) if self.delete_url else None
        settings.update(self.get_extra_settings())
        settings.update(self._settings_ovr)

        if('ajax' in request.GET and request.GET['ajax'] == 'true'):
            return render(request,self.ajax_template,settings)
        else:
            return render(request,self.template,settings)

    def post(self,request,obj_id):
        obj = self.obj_klass.objects.get(id=obj_id)
        form = self.form_klass(request.POST,request.FILES,instance=obj)
        if(form.is_valid()):
            #Save object but don't commit
            obj = form.save(commit=False)
            #Run pre commit, save and post commit functions
            self.pre_commit(obj,request=request)
            obj.save()
            self.post_commit(obj,request=request)

            #TODO custom save messages
            messages.success(request,'Saved')
            obj.log_change(request.user,'changed',form)
            form = self.form_klass(instance=obj)

            if(self.redirect_page):
                try:
                    return redirect(reverse(self.redirect_page,kwargs={'obj_id':obj.id}))
                except NoReverseMatch,e:
                    return redirect(reverse(self.redirect_page))


        else:
            messages.error(request,'There was an error in the form')

        settings = {'f':form}
        settings['delete_url'] = reverse(self.delete_url,kwargs={'obj_id':obj_id}) if self.delete_url else None
        settings.update(self.get_extra_settings())
        settings.update(self._settings_ovr)

        return render(request,self.template,settings)


    def pre_commit(self,obj,request=None):
        '''After form validation, but pre save'''
        pass

    def post_commit(self,obj,request=None):
        '''After saving the objct'''
        pass


class NewObjView(EditObjView):
    '''creates a new object'''
    _settings_ovr = {'edit':False}
    redirect_page = ''

    def post(self,request):
        ajax = 'ajax' in request.POST and request.POST['ajax'] == 'true'
        form = self.form_klass(request.POST,request.FILES)
        if(form.is_valid()):
            #Save object but don't commit
            obj = form.save(commit=False)
            #Run pre commit, save and post commit functions
            self.pre_commit(obj,request=request)
            obj.save()
            self.post_commit(obj,request=request)

            #todo custom save messages
            if(ajax):
                obj.log_creation(request.user,'Added (quickly)',)
            else:
                messages.success(request,'added')
                obj.log_creation(request.user,'Added',)

            if(ajax):
                if(hasattr(obj,'to_json')):
                    obj_json =json.dumps(obj.to_json())
                    return HttpResponse('OK\n%d,%s\n%s' % (obj.id,obj,obj_json)) #TODO escape the object here
                else:
                    return HttpResponse('OK\n%d,%s' % (obj.id,obj)) #TODO escape the object here

            else:
                try:
                    return redirect(reverse(self.redirect_page,kwargs={'obj_id':obj.id}))
                except NoReverseMatch,e:
                    return redirect(reverse(self.redirect_page))

        else:
            if(not ajax):
                messages.error(request,'There was an error in the form')
            else:
                print request.POST,form.errors

        settings = {'f':form}
        settings.update(self.get_extra_settings())
        if(ajax):
            return render(request,self.ajax_template,settings)
        else:
            return render(request,self.template,settings)

    def get(self,request):
        form = self.form_klass()
        settings = {'f':form}
        settings.update(self.get_extra_settings())
        settings.update(self._settings_ovr)
        if('ajax' in request.GET and request.GET['ajax'] == 'true'):
            return render(request,self.ajax_template,settings)
        else:
            return render(request,self.template,settings)


def getattr_from_func(obj,attr):
    attr = getattr(obj,attr)

    if(ismethod(attr) or isfunction(attr)):
        return attr()
    else:
        return attr

class TableObjView(EditObjView):
    '''Displays all the objects as a table, with a new button
    '''
    template = 'bootstrapform/generic_list.html'
    ajax_template = 'bootstrapform/generic_list_ajax.html'
    edit_url = ''
    new_url = ''
    page = False
    page_size = 6

    filter_res = True
    columns = (('ID','id'),)

    order_by = ['-id']

    def get_extra_settings(self):
        settings = super(TableObjView,self).get_extra_settings()
        settings['edit_url'] = self.edit_url
        settings['new_url'] = self.new_url

        return settings

    def get(self,request):
        objs = self.get_objects(request)
        heading = self.make_table_heading(request)
        rows = [[obj.id,self.make_table_row(obj)] for obj in objs]

        settings = {'objects':objs,
                    'heading':heading,
                    'rows':rows,
                    'filter':self.filter_res,
                    'use_page':self.page
                    }


        if(self.page):
            p = int(request.GET.get('p',0))
            total_pages = int(ceil(self.total_objects()/self.page_size))

            settings['current_page'] = p
            if(p > 0):
                settings['last_page'] = p -1
            if(p < (total_pages-1) ):
                settings['next_page'] = p +1

            settings['page_itterator'] = range(total_pages)

        settings.update(self.get_extra_settings())
        settings.update(self._settings_ovr)
        if('ajax' in request.GET and request.GET['ajax'] == 'true'):
            return render(request,self.ajax_template,settings)
        else:
            return render(request,self.template,settings)


    def total_objects(self):
        return self.obj_klass.objects.all().count()

    def get_objects(self,request):
        '''Gets all the objects to put in the gable'''
        o  = self.obj_klass.objects
        for v in self.order_by:
            o = o.order_by(v)

        if(self.page):
            p = int(request.GET.get('p',0))
            o = o[p*self.page_size:(p+1)*self.page_size]

        return o


    def make_table_row(self,obj):
        '''Returns a row of the table for obj (obj)'''
        return [getattr_from_func(obj,x) for x in zip(*self.columns)[1]]

    def make_table_heading(self,request):
        '''Returns the table heading '''
        return zip(*self.columns)[0]



class PagedByValueObjView(TableObjView):
    '''List all objects, but group them buy something e.g. last name'''
    search_field = ''
    value_itterator = '' #e.g. ['a','b','c','d','e','f']
    default_value = '' #e.g. a
    template = 'bootstrapform/indexed_list.html'
    ajax_template = 'bootstrapform/indexed_list_ajax.html'

    def get_filtered_objects(self,value):
        raise NotImplementedError


    def get_objects(self,request):
        p = request.GET.get('p',self.default_value)
        if(p in self.value_itterator):
            o = self.get_filtered_objects(p)
            for v in self.order_by:
                o = o.order_by(v)
            return o
        else:
            raise Exception('%s not in %s' % (p,self.value_itterator))

    def get(self,request):
        objs = self.get_objects(request)
        heading = self.make_table_heading(request)
        rows = [[obj.id,self.make_table_row(obj)] for obj in objs]

        settings = {'objects':objs,
                    'heading':heading,
                    'rows':rows,
                    'current_page':request.GET.get('p',self.default_value),
                    'page_itterator':self.value_itterator,
                    'filter':self.filter_res,
                    }


        settings.update(self.get_extra_settings())
        settings.update(self._settings_ovr)
        if('ajax' in request.GET and request.GET['ajax'] == 'true'):
            return render(request,self.ajax_template,settings)
        else:
            return render(request,self.template,settings)





