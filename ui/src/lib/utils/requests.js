/**
  IRIS Source Code
  Copyright (C) 2024 - DFIR-IRIS
  contact@dfir-iris.org

  This program is free software; you can redistribute it and/or
  modify it under the terms of the GNU Lesser General Public
  License as published by the Free Software Foundation; either
  version 3 of the License, or (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public License
  along with this program; if not, write to the Free Software Foundation,
  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
*/

let current_cid = null;

function get_caseid() {
    if (current_cid === null) {
        let queryString = window.location.search;
        let urlParams = new URLSearchParams(queryString);

        current_cid = urlParams.get('cid')
    }
    return current_cid
}

function case_param() {
    var params = {
        cid: get_caseid
    }
    return '?'+ $.param(params);
}

function post_request_api(uri, data, propagate_api_error, beforeSend_fn, cid, onError_fn) {
   if (cid === undefined ) {
     cid = case_param();
   } else {
     cid = '?cid=' + cid;
   }

   if (data === undefined || data === null) {
        data = JSON.stringify({
            'csrf_token': $('#csrf_token').val()
        });
   }

   return $.ajax({
        url: uri + cid,
        type: 'POST',
        data: data,
        dataType: "json",
        contentType: "application/json;charset=UTF-8",
        beforeSend: function(jqXHR, settings) {
            if (typeof beforeSend_fn === 'function') {
                beforeSend_fn(jqXHR, settings);
            }
        },
        error: function(jqXHR) {
            if (propagate_api_error) {
                if (jqXHR.responseJSON && jqXHR.status == 400) {
                    propagate_form_api_errors(jqXHR.responseJSON.data);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            } else {
                if (jqXHR.responseJSON) {
                    notify_error(jqXHR.responseJSON.message);
                } else {
                    ajax_notify_error(jqXHR, this.url);
                }
            }
        }
    });
}

export {
    case_param,
    get_caseid,
    post_request_api
};