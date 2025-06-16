import * as icons from '../view/elements/Card.icons.js'

export function formInfoSetup(form_creator, closeCallback) {
  const formContainer = document.createElement('div')
  update()
  return formContainer

  function update() {
    const formHtml = getHtml(form_creator)

    formContainer.innerHTML = formHtml;

    setupEventListeners()

    return formContainer
  }

  function setupEventListeners() {
    const form = formContainer.querySelector('form');
    form.addEventListener('submit', form_creator.onSubmit);

    const cancel_btn = form.querySelector('.f3-cancel-btn');
    cancel_btn.addEventListener('click', onCancel)

    const edit_btn = form.querySelector('.f3-edit-btn');
    if (edit_btn) edit_btn.addEventListener('click', onEdit)

    const delete_btn = form.querySelector('.f3-delete-btn');
    if (delete_btn && form_creator.onDelete) {
      delete_btn.addEventListener('click', form_creator.onDelete);
    }

    const add_relative_btn = form.querySelector('.f3-add-relative-btn');
    if (add_relative_btn && form_creator.addRelative) {
      add_relative_btn.addEventListener('click', () => {
        if (form_creator.addRelativeActive) form_creator.addRelativeCancel()
        else form_creator.addRelative()
        form_creator.addRelativeActive = !form_creator.addRelativeActive
        update()
      });
    }

    const upload_btn = form.querySelectorAll('.f3-upload-btn').forEach(btn => {

      btn.addEventListener("click", () => {
        const id = btn.id.replace("upload_", "").replace("_btn", "");
        const fileInput = document.getElementById(`file_${id}`);
        if (fileInput) fileInput.click();
      });
    })

    const close_btn = form.querySelector('.f3-close-btn');
    close_btn.addEventListener('click', closeCallback)

    if (form_creator.other_parent_field) {
      cancel_btn.style.display = 'none'
    }

    function onCancel() {
      form_creator.editable = false
      if (form_creator.onCancel) form_creator.onCancel()
      update()
    }

    function onEdit() {
      form_creator.editable = !form_creator.editable
      update()
    }
  }
}

function getHtml(form_creator) {
  return (` 
    <form id="familyForm" class="f3-form ${form_creator.editable ? '' : 'non-editable'}">
      ${closeBtn()}
      ${form_creator.title ? `<h3 class="f3-form-title">${form_creator.title}</h3>` : ''}
      <div style="text-align: right; display: ${form_creator.new_rel ? 'none' : 'block'}">
        ${form_creator.addRelative && !form_creator.no_edit ? addRelativeBtn() : ''}
        ${form_creator.no_edit ? spaceDiv() : editBtn()}
      </div>
      ${genderRadio()}

      ${fields()}

      ${form_creator.other_parent_field ? otherParentField() : ''}

      ${form_creator.onDelete ? deleteBtn() : ''}
      
      <div class="f3-form-buttons">
        <button type="button" class="f3-cancel-btn">Cancel</button>
        <button type="submit">Submit</button>
      </div>
    </form>
  `)

  function deleteBtn() {
    return (`
      <div>
        <button type="button" class="f3-delete-btn" ${form_creator.can_delete ? '' : 'disabled'}>
          Delete
        </button>
      </div>
    `)
  }

  function addRelativeBtn() {
    return (`
      <span class="f3-add-relative-btn">
        ${form_creator.addRelativeActive ? icons.userPlusCloseSvgIcon() : icons.userPlusSvgIcon()}
      </span>
    `)
  }

  function editBtn() {
    return (`
      <span class="f3-edit-btn">
        ${form_creator.editable ? icons.pencilOffSvgIcon() : icons.pencilSvgIcon()}
      </span>
    `)
  }

  function genderRadio() {
    if (!form_creator.editable) return ''
    return (`
      <div class="f3-radio-group">
        ${form_creator.gender_field.options.map(option => (`
          <label>
            <input type="radio" name="${form_creator.gender_field.id}" 
              value="${option.value}" 
              ${option.value === form_creator.gender_field.initial_value ? 'checked' : ''}
            >
            ${option.label}
          </label>
        `)).join('')}
      </div>
    `)
  }

  function fields() {
    if (!form_creator.editable) return infoField()
    return form_creator.fields.map(field => (`
      ${field.type === 'text' || field.type === 'date' || field.type.startsWith('datetime') ? `
        <div class="f3-form-field">
          <label>${field.label}</label>
          <input type="${field.type}" 
            name="${field.id}" 
            value="${field.initial_value || ''}"
            placeholder="${field.label}">
        </div>
      ` : field.type === 'textarea' ? `
        <div class="f3-form-field">
          <label>${field.label}</label>
          <textarea name="${field.id}" 
            placeholder="${field.label}">${field.initial_value || ''}</textarea>
        </div>
      ` : field.type === 'image' || field.type === 'file' ?
        `<div>
          <input id="file_${field.id}" type="file" name="${field.id}" hidden>
          <button id="upload_${field.id}_btn" class="f3-upload-btn" type="button" data-input="file_${field.id}">
            Upload ${field.label}
          </button>
        </div>`
        : ''}
    `)).join('')

    function infoField() {
      const avatarField = form_creator.fields.find(
        (f) => f.id === "avatar" || f.type === "image",
      );
      var gender =
        form_creator.gender_field.initial_value == "M"
          ? "male"
          : "female";

      const otherFields = form_creator.fields.filter(
        (f) => f.id !== "avatar" || f.type !== "image",
      );

      // put avatar field at the top
      const orderedFields = avatarField
        ? [avatarField, ...otherFields]
        : otherFields;

      return orderedFields
        .map((field) => {
          const value = field.initial_value || "";
          if (
            field.id === "avatar" &&
            value.startsWith("data:image")
          ) {
            return `
                  <div class="form-avatar gender-${gender}">
                      <img src="${value}" alt="Avatar" style="max-width: 100%;">
                  </div>`;
          } else if (
            field.id === "avatar" &&
            value.length === 0
          ) {
            return `<div class="form-avatar">
                      <div class="card-inner card-image-circle card-${gender}" style="margin: auto;">
                          <div class="person-icon">
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" style="fill: currentColor" data-icon="person">
                                  <g data-icon="person">
                                      <path d="M256 288c79.5 0 144-64.5 144-144S335.5 0 256 0 112 
                                          64.5 112 144s64.5 144 144 144zm128 32h-55.1c-22.2 10.2-46.9 16-72.9 16s-50.6-5.8-72.9-16H128C57.3 320 0 377.3 
                                          0 448v16c0 26.5 21.5 48 48 48h416c26.5 0 48-21.5 48-48v-16c0-70.7-57.3-128-128-128z"></path>
                                  </g>
                              </svg>
                          </div>
                      </div>
                  </div>`;
          } else if (value.length > 0) {
            return `
                  <div class="f3-info-field">
                    <span class="f3-info-field-label">${field.label}</span>
                    <span class="f3-info-field-value">${value}</span>
                  </div>`;
          }
        })
        .join("");
    }
  }

  function otherParentField() {
    return (`
      <div class="f3-form-field">
        <label>${form_creator.other_parent_field.label}</label>
        <select name="${form_creator.other_parent_field.id}">
          ${form_creator.other_parent_field.options.map(option => `
            <option value="${option.value}" 
              ${option.value === form_creator.other_parent_field.initial_value ? 'selected' : ''}>
              ${option.label}
            </option>
          `).join('')}
        </select>
      </div>
    `)
  }

  function closeBtn() {
    return (`
      <span class="f3-close-btn">
        ×
      </span>
    `)
  }

  function spaceDiv() {
    return `<div style="height: 24px;"></div>`
  }
}

