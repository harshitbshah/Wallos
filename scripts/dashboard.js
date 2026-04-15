let quickEditData = null;

function openQuickEdit(id) {
  fetch(`endpoints/subscription/get.php?id=${id}`)
    .then(r => r.json())
    .then(data => {
      quickEditData = data;

      document.getElementById('quick-edit-title').textContent = data.name;
      document.getElementById('quick-edit-name').textContent = data.name;

      const logo = document.getElementById('quick-edit-logo');
      if (data.logo) {
        logo.src = `images/uploads/logos/${data.logo}`;
        logo.style.display = 'inline-block';
      } else {
        logo.style.display = 'none';
      }

      document.getElementById('quick-edit-price').value = data.price;
      document.getElementById('quick-edit-currency').value = data.currency_id;
      document.getElementById('quick-edit-next-payment').value = data.next_payment;
      document.getElementById('quick-edit-auto-renew').checked = data.auto_renew == 1;
      document.getElementById('quick-edit-full-link').href = `subscriptions.php?edit=${id}`;

      document.getElementById('quick-edit-modal').classList.add('is-open');
      document.body.classList.add('no-scroll');
    })
    .catch(() => showErrorMessage(translate('failed_to_load_subscription')));
}

function closeQuickEdit() {
  document.getElementById('quick-edit-modal').classList.remove('is-open');
  document.body.classList.remove('no-scroll');
  quickEditData = null;
}

function saveQuickEdit() {
  if (!quickEditData) return;

  const formData = new FormData();
  formData.append('id', quickEditData.id);
  formData.append('name', quickEditData.name);
  formData.append('price', document.getElementById('quick-edit-price').value);
  formData.append('currency_id', document.getElementById('quick-edit-currency').value);
  formData.append('next_payment', document.getElementById('quick-edit-next-payment').value);
  formData.append('auto_renew', document.getElementById('quick-edit-auto-renew').checked ? 1 : 0);
  formData.append('start_date', quickEditData.start_date || '');
  formData.append('frequency', quickEditData.frequency);
  formData.append('cycle', quickEditData.cycle);
  formData.append('notes', quickEditData.notes || '');
  formData.append('payment_method_id', quickEditData.payment_method_id);
  formData.append('payer_user_id', quickEditData.payer_user_id);
  formData.append('category_id', quickEditData.category_id);
  formData.append('notify', quickEditData.notify);
  formData.append('inactive', quickEditData.inactive);
  formData.append('url', quickEditData.url || '');
  formData.append('notify_days_before', quickEditData.notify_days_before ?? -1);
  formData.append('cancellation_date', quickEditData.cancellation_date || '');
  formData.append('replacement_subscription_id', quickEditData.replacement_subscription_id || 0);
  formData.append('logo-url', '');

  fetch('endpoints/subscription/add.php', {
    method: 'POST',
    headers: { 'X-CSRF-Token': window.csrfToken },
    body: formData
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'Success') {
        closeQuickEdit();
        showSuccessMessage(data.message);
        setTimeout(() => location.reload(), 800);
      } else {
        showErrorMessage(data.message || translate('error'));
      }
    })
    .catch(() => showErrorMessage(translate('error')));
}

document.addEventListener("DOMContentLoaded", function () {
  function updateAiRecommendationNumbers() {
    document.querySelectorAll(".ai-recommendation-item").forEach(function (item, index) {
      const numberSpan = item.querySelector(".ai-recommendation-header h3 > span");
      if (numberSpan) {
        numberSpan.textContent = `${index + 1}. `;
      }
    });
  }

  document.querySelectorAll(".ai-recommendation-item").forEach(function (item) {
    item.addEventListener("click", function () {
      item.classList.toggle("expanded");
    });
  });

  document.querySelectorAll(".delete-ai-recommendation").forEach(function (el) {
    el.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();

      const item = el.closest(".ai-recommendation-item");
      const id = item.getAttribute("data-id");

      fetch("endpoints/ai/delete_recommendation.php", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": window.csrfToken,
        },
        body: JSON.stringify({ id: id }),
      })
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            item.remove();
            updateAiRecommendationNumbers();
            showSuccessMessage(translate("success"));
          } else {
            showErrorMessage(data.message || translate("failed_delete_ai_recommendation"));
          }
        })
        .catch(error => {
          console.error(error);
          showErrorMessage(translate("unknown_error"));
        });
    });
  });

});

