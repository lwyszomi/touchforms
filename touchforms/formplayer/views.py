from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views.decorators.http import require_POST
from touchforms.formplayer.models import XForm
from touchforms.formplayer.autocomplete import autocompletion, DEFAULT_NUM_SUGGESTIONS
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseNotFound
from django.core.urlresolvers import reverse
import logging
import json
from collections import defaultdict
from touchforms.formplayer.signals import xform_received
from django.template.context import RequestContext
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
import tempfile
import os
from . import api
from touchforms.formplayer.api import DjangoAuth
from django.contrib.auth.decorators import login_required
from touchforms.formplayer.const import PRELOADER_TAG_UID

@login_required
def xform_list(request):
    forms_by_namespace = defaultdict(list)
    success = True
    notice = ""
    if request.method == "POST":
        if "file" in request.FILES:
            file = request.FILES["file"]
            try:
                tmp_file_handle, tmp_file_path = tempfile.mkstemp()
                tmp_file = os.fdopen(tmp_file_handle, 'w')
                tmp_file.write(file.read())
                tmp_file.close()
                XForm.from_file(tmp_file_path, str(file))
                notice = "Created form: %s " % file
            except Exception, e:
                logging.error("Problem creating xform from %s: %s" % (file, e))
                success = False
                notice = "Problem creating xform from %s: %s" % (file, e)
        else:
            success = False
            notice = "No uploaded file set."
            
    for form in XForm.objects.all():
        forms_by_namespace[form.namespace].append(form)
    return render_to_response("formplayer/xform_list.html", {
            'forms_by_namespace': dict(forms_by_namespace),
            "success": success,
            "notice": notice
        }, context_instance=RequestContext(request))
                              
def download(request, xform_id):
    """
    Download an xform
    """
    xform = get_object_or_404(XForm, id=xform_id)
    try:
        contents = xform.file.read()
    except IOError:
        # file not found, don't fail hard as in a multi-worker environment
        # this method is just kind of deprecated.
        return HttpResponseNotFound("Sorry that form is no longer available.")
    else:
        response = HttpResponse(mimetype='application/xml')
        response.write(contents)
        return response


def coalesce(*args):
    for arg in args:
        if arg is not None:
            return arg
    return None

@csrf_exempt
def enter_form(request, **kwargs):
    xform_id = kwargs.get('xform_id')
    xform = kwargs.get('xform')
    instance_xml = kwargs.get('instance_xml')
    session_data = coalesce(kwargs.get('session_data'), {})
    input_mode = coalesce(kwargs.get('input_mode'), 'touch')
    submit_callback = coalesce(kwargs.get('onsubmit'), default_submit)
    abort_callback = coalesce(kwargs.get('onabort'), default_abort)
    force_template = coalesce(kwargs.get('force_template'), None)
    offline_mode = kwargs.get('offline', False)

    # support for backwards compatibility; preloaders are DEPRECATED
    preload_data = kwargs.get('preloader_data')
    if preload_data:
        session_data['preloaders'] = preload_data

    if not xform:
        xform = get_object_or_404(XForm, id=xform_id)
        
    if request.method == "POST":
        if request.POST["type"] == 'form-complete':
            instance_xml = request.POST["output"]
            return form_entry_complete(request, xform, instance_xml, 
                                       submit_callback)

        elif request.POST["type"] == 'form-aborted':
            return form_entry_abort(request, xform, abort_callback)

    return form_entry_new(request, xform, instance_xml, session_data, 
                          input_mode, offline_mode, force_template)

def form_entry_new(request, xform, instance_xml, session_data, input_mode, 
                   offline_mode, force_template=None):
    """start a new touchforms/typeforms session"""
    if force_template is not None:
        templ = force_template
    else:
        templ = {
            'touch': 'touchforms/touchscreen.html',
            'type': 'typeforms.html',
            'full': 'fullform.html',
        }[input_mode]
    if offline_mode:
        touchforms_url = 'http://localhost:%d' % settings.OFFLINE_TOUCHFORMS_PORT
    else:
        touchforms_url = reverse('xform_player_proxy')
    return render_to_response(templ, {
            "touchforms_url": touchforms_url,
            "form": xform,
            "mode": 'xform',
            "instance_xml": json.dumps(instance_xml),
            "session_data": json.dumps(session_data),
            "dim": get_player_dimensions(request),
            "fullscreen": request.GET.get('mode', '').startswith('full'),
            "lang": request.GET.get('lang'),
            'maps_api_key': settings.GMAPS_API_KEY,
        }, context_instance=RequestContext(request))

def form_entry_abort(request, xform, callback):
    """handle an aborted form entry session"""
    return callback(xform)

def form_entry_complete(request, xform, instance_xml, callback):
    """handle a completed form entry session (xform finished and submitted)"""
    xform_received.send(sender="player", instance=instance_xml)
    return callback(xform, instance_xml)

def default_submit(xform, instance_xml):
    response = HttpResponse(mimetype='application/xml')
    response.write(instance_xml)
    return response

def default_abort(xform, abort_url='/'):
    return HttpResponseRedirect(abort_url)

# this function is here for backwards compatibility (just BHOMA?); use enter_form() instead
def play(request, xform_id, callback=None, preloader_data=None, input_mode=None,
         abort_callback=default_abort, force_template=None):
    """
    Play an XForm.

    xform_id - which xform to play
    callback(xform, instance_xml) - action to perform when form is submitted or aborted (both via POST) 
        default behavior is to display the xml, and return to the form list, respectively
        for abort, instance_xml will be None
    preloader_data - data to satisfy form preloaders: {preloader type => {preload param => preload value}} 
    input_mode - 'touch' for touchforms, 'type' for typeforms
    instance_xml - an xml instance that, if present, will be edited during the form session
    """

    return enter_form(request,
                      xform_id=xform_id,
                      preloader_data=preloader_data,
                      input_mode=input_mode,
                      onsubmit=callback,
                      onabort=abort_callback,
                      force_template=force_template,
                      )

def get_player_dimensions(request):
    def get_dim(getparam, settingname):
        dim = request.GET.get(getparam)
        if not dim:
            try:
                dim = getattr(settings, settingname)
            except AttributeError:
                pass
        return dim

    return {
        'width': get_dim('w', 'TOUCHSCREEN_WIDTH'),
        'height': get_dim('h', 'TOUCHSCREEN_HEIGHT')
    }

@csrf_exempt
@require_POST
def player_proxy(request):
    """
    Proxy to an xform player, to avoid cross-site scripting issues
    """
    data = request.raw_post_data
    auth_cookie = request.COOKIES.get('sessionid')
    response = api.post_data(data, settings.XFORMS_PLAYER_URL, 
                             content_type="text/json", auth=DjangoAuth(auth_cookie))
    return HttpResponse(response)

# DEPRECATED    
def api_preload_provider(request):
    param = request.GET.get('param', "")
    param = param.strip().lower()

    value = param
    if param == PRELOADER_TAG_UID:
        import uuid
        value = uuid.uuid4().hex

    return HttpResponse(value)

def api_autocomplete(request):
    domain = request.GET.get('domain')
    key = request.GET.get('key', '')
    max_results = int(request.GET.get('max', str(DEFAULT_NUM_SUGGESTIONS)))

    if domain is None or key is None or max_results is None:
        return HttpResponse("Please specify 'domain', 'key' and 'max' parameters.", status=400)

    try:
        response = HttpResponse(json.dumps(autocompletion(domain, key, max_results)), 'text/json')
    except Exception:
        logging.error("Exception on getting response from api_autocomplete")
        return HttpResponse(status=500)

    return response

def player_abort(request):
    class TimeoutException(Exception):
        pass

    try:
        raise TimeoutException("A touchscreen view has timed out and was aborted")
    except TimeoutException:
        logging.exception('')

    try:
        redirect_to = reverse(settings.TOUCHFORMS_ABORT_DEST)
    except AttributeError:
        redirect_to = '/'

    return HttpResponseRedirect(redirect_to)
