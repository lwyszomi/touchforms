

function loadForm (formName) {
  jQuery.post(XFORM_URL, JSON.stringify({'action': 'new-form', 'form-name': formName}), function (resp) {
    gSessionID = resp["session_id"];
    renderEvent(resp["event"], true);
  }, "json");
}

function renderEvent (event, dirForward) {
  if (event["type"] == "question") {
    renderQuestion(event);
  } else if (event["type"] == "form-complete") {
    formComplete(event);
  } else if (event["type"] == "sub-group") {
    if (event["repeatable"]) {
      alert("i can't support repeats right now!");
    }
  
    jQuery.post(XFORM_URL, JSON.stringify({'action': (dirForward ? 'next' : 'back'), 'session-id': gSessionID}), function (resp) {
      renderEvent(resp["event"], dirForward || resp["at-start"]);
    }, "json");
  } else {
    alert("unrecognized event [" + event["type"] + "]");
  }
}

/*
    <button onClick="questionEntry.update(freeEntry); answerBar.update(freeTextAnswer); freeEntryKeyboard.update(numPad);">numeric entry</button>
    <button onClick="questionEntry.update(freeEntry); answerBar.update(freeTextAnswer); freeEntryKeyboard.update(keyboard);">text entry</button>
    <button onClick="questionEntry.update(choiceSelect(['Male', 'Female'], []));">multiple choice</button>
    <button onClick="questionEntry.update(freeEntry); answerBar.update(dateAnswer); freeEntryKeyboard.update(decadeChoices);">date: year 1/2</button>
    <button onClick="questionEntry.update(freeEntry); answerBar.update(dateAnswer); freeEntryKeyboard.update(yearSelect(1990));">date: year 2/2</button>
    <button onClick="questionEntry.update(freeEntry); answerBar.update(dateAnswer); freeEntryKeyboard.update(monthChoices);">date: month</button>
    <button onClick="questionEntry.update(freeEntry); answerBar.update(dateAnswer); freeEntryKeyboard.update(daySelect(29));">date: day</button>
*/
    
function renderQuestion (event) {
  activeQuestion = event;
  questionCaption.setText(event["caption"]);
 
  if (event["datatype"] == "str" ||
      event["datatype"] == "int" ||
      event["datatype"] == "float") {
    questionEntry.update(freeEntry);
    answerBar.update(freeTextAnswer);
    freeEntryKeyboard.update(event["datatype"] == 'str' ? keyboard : numPad);    
    
    if (event["answer"] != null) {
      answerText.setText(event["answer"]);
    }
  } else if (event["datatype"] == "select" || event["datatype"] == "multiselect") {
    for (i = 0; i < event["choices"].length; i++) {
      ord = i + 1;
    
      caption = document.createElement("span");
      caption.textContent = event["choices"][i] + "   ";
    
      input = document.createElement("input");
      input.type = (event["datatype"] == "select" ? "radio" : "checkbox");
      input.name = "select";
      input.value = ord;
      if (event["answer"] != null) {
        input.checked = (event["datatype"] == "select" ? ord == event["answer"] : event["answer"].indexOf(ord) != -1);
      }
        
      _$("control").appendChild(caption);
      _$("control").appendChild(input);
      _$("control").appendChild(document.createElement("br"));
    }
  } else if (event["datatype"] == "info") {
    questionEntry.update(null);
  } else {
    alert("unrecognized datatype [" + event["datatype"] + "]");
  }
}

function getQuestionAnswer () {
  type = activeQuestion["datatype"];

  if (type == "str" || type == "int" || type == "float") {
    return answerText.child.control.value;
  } else if (type == "select" || type == "multiselect") {
    answer = [];
    choices = document.getElementsByName("select");
    for (i = 0; i < choices.length; i++) {
      choice = choices[i];
      if (choice.checked) {
        answer.push(choice.value);
      }
    }
    
    if (type == "select") {
      return answer.length > 0 ? answer[0] : null;
    } else {
      return answer;
    }
  } else if (type == "info") {
    return null;
  }
}

function answerQuestion () {
  answer = getQuestionAnswer();
  
  jQuery.post(XFORM_URL, JSON.stringify({'action': 'answer', 'session-id': gSessionID, 'answer': answer}), function (resp) {
    if (resp["status"] == "validation-error") {
      if (resp["type"] == "required") {
        showError("An answer is required");
      } else if (resp["type"] == "constraint") {
        showError(resp["reason"]);      
      }
    } else {
      renderEvent(resp["event"], true);
    }
  }, "json");
}

function prevQuestion () {
  jQuery.post(XFORM_URL, JSON.stringify({'action': 'back', 'session-id': gSessionID}), function (resp) {
    renderEvent(resp["event"], false);
  }, "json");
}

function post_to_url(path, params, method) {
    // hat tip: http://stackoverflow.com/questions/133925/javascript-post-request-like-a-form-submit
    method = method || "post"; // Set method to post by default, if not specified.
    // The rest of this code assumes you are not using a library.
    // It can be made less wordy if you use one.
    
    var form = document.createElement("form");
    form.setAttribute("method", method);
    form.setAttribute("action", path);

    for(var key in params) {
        var hiddenField = document.createElement("input");
        hiddenField.setAttribute("type", "hidden");
        hiddenField.setAttribute("name", key);
        hiddenField.setAttribute("value", params[key]);

        form.appendChild(hiddenField);
    }

    form.submit();
}
function formComplete (event) {
    // POST the response back to ourselves for further processing
    post_to_url("", event)
}
