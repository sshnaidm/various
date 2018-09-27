// ==UserScript==
// @name     _Convert displayed times from browsers timezone to UTC
// @include  /^https?://review\.(openstack|rdoproject)\.org/(r/)?(#/c/)?\d*?/?(\d*)?/?$/
// @require  https://ajax.googleapis.com/ajax/libs/jquery/2.1.0/jquery.min.js
// @require  https://gist.github.com/raw/2625891/waitForKeyElements.js
// @require  https://momentjs.com/downloads/moment.min.js
// @require  https://momentjs.com/downloads/moment-timezone-with-data-2012-2022.min.js
// @grant    GM_addStyle
// ==/UserScript==
//- The @grant directive is needed to restore the proper sandbox.

const pagesTimezone     = Intl.DateTimeFormat().resolvedOptions().timeZone; // get timezone from browser
const desiredTimezone   = "Etc/UTC";  // new timezone

// take all times from gerrit page with that class
waitForKeyElements ("div.com-google-gerrit-client-change-Message_BinderImpl_GenCss_style-date", convertTimezone); // installed script line

function convertTimezone (jNode) {

  var timeStr = jNode.text ().trim ();
  var origTime = moment.tz (timeStr, ["MMM DD hh:mm A", "hh:mm A", "MMM DD HH:mm", "HH:mm"], pagesTimezone);
  var utcnow = moment.utc().format("MM DD");
  var tsnow = moment.utc(origTime).format("MM DD")
  var today = utcnow == tsnow;

  if (timeStr.includes("AM") || timeStr.includes("PM")) {
  	var utcTime   = (today)? origTime.tz (desiredTimezone).format ("hh:mm A z"):origTime.tz (desiredTimezone).format ("MMM DD hh:mm A z");
  }
  else {
  	var utcTime   = (today)? origTime.tz (desiredTimezone).format ("HH:mm z"):origTime.tz (desiredTimezone).format ("MMM DD HH:mm z");
  }

    jNode.text (utcTime);
}
