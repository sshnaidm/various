// ==UserScript==
// @name     Gerrit RDO Zuul Status
// @author   Michel Peterson
// @version  4
// @grant    none
// @include  /^https?://review\.rdoproject\.org/r/(#/c/)?\d*?/?(\d*)?/?$/
// @require  https://code.jquery.com/jquery-3.3.1.min.js
// ==/UserScript==

// Config

const zuul_status_base = "https://softwarefactory-project.io/zuul/api/tenant/rdoproject.org/";
const zuul_status_url = zuul_status_base + "status/change/";
const zuul_runjob_url = "https://review.rdoproject.org/zuul/";

// /Config

// Script start

$('style#gerrit_sitecss').append('.result_RUNNING { color: #1e9ced; }');

// this regex matches "Patch set #"
var psRegex = /^(Uploaded patch set|Patch Set) (\d+)(:|\.)/;

var parse_comments = function() {
    var comments = [];
    $("p").each(function() {
        var match = psRegex.exec($(this).html());
        if (match !== null) {
            var psnum = parseInt(match[2]);
            var top = $(this).parent().parent().parent();
            // old change screen
            var name = top.attr("name");
            if (!name) {
                // new change screen
                name = $(this).parent().parent().parent().children().children()[0].innerHTML;
                top = $(this).parent().parent().parent().parent();
            }
            var comment = {};
            comment.name = name;

            var date_cell = top.find(".commentPanelDateCell");
            if (date_cell.attr("title")) {
                // old change screen
                comment.date = date_cell.attr("title");
            } else {
                // new change screen
                comment.date = $(this).parent().parent().parent().children().children()[2].innerHTML
            }
            var comment_panel = $(this).parent();
            comment.psnum = psnum;
            comments.push(comment);
        }
    });
    return comments;
};

var latest_patchset = function(comments) {
    var psnum = 0;
    for (var i = 0; i < comments.length; i++) {
        psnum = Math.max(psnum, comments[i].psnum);
    }
    return psnum;
};

var render = function(jobs) {
  var location = $('table.test_result_table');

  var table = '<tbody>' +
      '<tr>' + 
      '<td class="header">Zuul check</td>' +
      '<td class="header ci_date result_WARNING">Still running</td>' +
      '</tr>';

  $.each(jobs, function(i, job) {
      var status_with_completeness = ((job.status === 'running' && typeof job.completeness !== 'undefined') ? 'RUNNING (' + job.completeness + ')' : job.status.toUpperCase());

      table += '<tr>' +
      '<td><a href="' + job.url + '" rel="nofollow">' + job.name + '</a></td>' +
      '<td><span class="comment_test_result"><span class="result_' + job.status.toUpperCase() +'">' + status_with_completeness + '</span></td>' +
      '</tr>';
  });

  table += '</tbody>';

  location.html(table);
};

var main = function() {
    const url = $(location).attr('href');
    const matches_url = /^https?:\/\/review\.rdoproject\.org\/r\/(#\/c\/)?(\d*)\/?(\d*)?\/?$/.exec(url);

    const change_id = matches_url[2];
    var change_ver = matches_url[3];

    if (typeof change_ver === 'undefined'){
        change_ver = latest_patchset(parse_comments());
    }

    var status_url = zuul_status_url + change_id + ',' + change_ver;


    $.getJSON(status_url, function(data) {
        var queue;
        var jobs = [];

        if (data.length === 0){
          if ($('.result_WARNING').length > 0){
              location.reload();
          }
          return;
        }

        for(i=0; i <= data.length; i++){
          queue = data[i];
          if (queue.items_behind.length == 0){
              break;
          }
        }

        if (!queue){
            console.log("couldn't find a queue");
            return;
        }

        $.each(queue.jobs, function(i, job) {
            var item = {};

            item.status = job.result ? job.result.toLowerCase() : (job.url ? 'running' : 'queued');
            item.name = job.name;
            item.pipeline = job.pipeline;
            item.url = job.result ? job.report_url : (job.url ? zuul_runjob_url + job.url : "#");

            if (item.status === 'running' && job.remaining_time !== null){
                item.completeness = Math.round(100 * (job.elapsed_time / (job.elapsed_time + job.remaining_time))) + '%';
            }

            jobs.push(item);

        });

        render(jobs);
        setTimeout(main, 2000);
    });
};


// So we refresh on each update.

MutationObserver = window.MutationObserver || window.WebKitMutationObserver;
var observer = new MutationObserver(function(mutations, observer) {
  var span = $("span.rpcStatus");
  $.each(mutations, function(i, mutation) {
    if (mutation.target === span[0] &&
        mutation.attributeName === "style" &&
        (!(span.is(":visible")))) {
      main();
    }
  });
});
observer.observe(document, {
  subtree: true,
  attributes: true
});