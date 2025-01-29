window.checkVersion = async function checkVersion() {
    try {
        const response = await fetch('/api/version');
        const data = await response.json();
        const currentVersion = localStorage.getItem('appVersion');
        
        if (!currentVersion) {
            localStorage.setItem('appVersion', data.version);
            return;
        }

        if (data.version !== currentVersion) {
            localStorage.setItem('appVersion', data.version);
            window.location.reload(true);
        }
    } catch (error) {
        console.error('Version check failed:', error);
    }
}

window.fetchUserInfo = async function(userID) {
    try {
        const response = await fetch('/api/v1/db/get_user_info', {
            method: 'POST',
            body: JSON.stringify({ user_id: userID }),
            headers: {
                'Content-Type': 'application/json'
            },
        });

        if (!response.ok) {
            throw new Error('Failed to fetch initial user data');
        }

        const data = await response.json();

        if (!data) {
            console.error('User could not be found!');
            return null;
        }

        return data;
    } catch (error) {
        console.error('Error fetching initial user data:', error);
        return null;
    }
};

window.selectDomain = async function selectDomain(domainId, userID) {
    try {
        const url = `/api/v1/qa/select_domain?userID=${encodeURIComponent(userID)}`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                domain_id: domainId
            })
        });

        if (!response.ok) {
            return 0;
        }

        const data = await response.json();
        
        if (data["message"] !== "success") {
            return 0;
        }

        return 1;

    } catch (error) {
        console.error('Error selecting domain', error);
        return 0;
    }
}

window.renameDomain = async function renameDomain(domainId, newName) {
    try {
        const response = await fetch('/api/v1/db/rename_domain', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                domain_id: domainId,
                new_name: newName
            })
        });

        if (!response.ok) {
            return 0;
        }

        const data = await response.json();
        
        if (data.message !== "success") {
            return 0;
        }

        return 1;

    } catch (error) {
        console.error('Error renaming domain:', error);
        return 0;
    }
};

window.createDomain = async function createDomain(userId, domainName) {
    try {
        const url = `/api/v1/db/create_domain?userID=${encodeURIComponent(userId)}`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                domain_name: domainName
            })
        });

        if (!response.ok) {
            return { success: 0, data: null };
        }

        const data = await response.json();
        
        if (data.message !== "success") {
            return { success: 0, id: null };
        }

        return { success: 1, id: data.domain_id };
    } catch (error) {
        console.error('Error creating domain:', error);
        return { success: 0, id: null };
    }
};

window.deleteDomain = async function deleteDomain(domainId) {
    try {
        const response = await fetch('/api/v1/db/delete_domain', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                domain_id: domainId
            })
        });

        const data = await response.json();
        
        if (!response.ok) {
            return {
                success: false,
                message: data.message
            };
        }

        if (data.message !== "success") {
            return {
                success: false,
                message: data.message
            };
        }

        return {
            success: true,
            message: "Domain successfully deleted"
        };

    } catch (error) {
        console.error('Error deleting domain:', error);
        return {
            success: false,
            message: "An unexpected error occurred"
        };
    }
};

window.storeFile = async function(userID, formData) {
    try {
        const response = await fetch(`/api/v1/io/store_file?userID=${encodeURIComponent(userID)}`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to store file');
        }

        const data = await response.json();
        
        if (data.message !== "success") {
            return 0;
        }

        return 1;

    } catch (error) {
        console.error('Error storing file:', error);
        return {
            success: false,
            error: error.message
        };
    }
};

window.uploadFiles = async function(userID) {
    try {
        const response = await fetch(`/api/v1/io/upload_files?userID=${userID}`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to process uploads');
        }

        const data = await response.json();
        
        if (data.message !== "success") {
            return {
                success: false,
                error: data.message || 'Upload process failed'
            };
        }

        return {
            success: true,
            data: {
                file_names: data.file_names,
                file_ids: data.file_ids,
                message: data.message
            }
        };

    } catch (error) {
        console.error('Error uploading files:', error);
        return {
            success: false,
            error: error.message
        };
    }
};

window.removeFile = async function(fileId, domainId, userId) {
    try {
        const url = `/api/v1/db/remove_file_upload?userID=${encodeURIComponent(userId)}`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                file_id: fileId,
                domain_id: domainId
            })
        });

        if (!response.ok) {
            throw new Error('Failed to remove files');
        }

        const data = await response.json();
        
        if (data.message !== "success") {
            return 0;
        }

        return 1;

    } catch (error) {
        console.error('Error removing files:', error);
        return {
            success: false,
            error: error.message
        };
    }
};

window.sendMessage = async function(message, userId, sessionId, fileIds) {
    if (!message) {
        return {
            message: "Please enter your sentence!",
            status: 400
        };
    }

    try {
        const url = `/api/v1/qa/generate_answer?userID=${encodeURIComponent(userId)}&sessionID=${encodeURIComponent(sessionId)}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                user_message: message,
                file_ids: fileIds
            })
        });

        const data = await response.json();

        if (!response.ok) {
            return {
                message: data.message || 'Server error!',
                status: response.status
            };
        }

        return {
            ...data,
            status: 200
        };

    } catch (error) {
        console.error('Error:', error);
        return {
            message: 'Error generating message!',
            status: 500
        };
    }
};

window.sendFeedback = async function(formData, userId) {
    try {
        const url = `/api/v1/db/insert_feedback?userID=${encodeURIComponent(userId)}`;
        
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to submit feedback');
        }

        const data = await response.json();
        
        return {
            success: true,
            message: data.message || 'Thank you for your feedback!'
        };

    } catch (error) {
        console.error('Error submitting feedback:', error);
        return {
            success: false,
            message: 'Failed to submit feedback. Please try again.'
        };
    }
}

window.sendRating = async function(ratingData, userNote, userId) {
    try {
        const url = `/api/v1/db/insert_rating?userID=${encodeURIComponent(userId)}`;
        const formData = new FormData();
        formData.append('rating', ratingData);
        
        if (userNote){
        formData.append('user_note', userNote);
        }

        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Failed to submit rating');
        }

        const data = await response.json();
        
        return {
            success: true,
            message: data.message || 'Thank you for your feedback!'
        };

    } catch (error) {
        console.error('Error submitting feedback:', error);
        return {
            success: false,
            message: 'Failed to submit feedback. Please try again.'
        };
    }
}

window.googleSignIn = async function googleSignIn() {
    try {
        const url = `/api/v1/qa/select_domain?userID=${encodeURIComponent(userID)}`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                domain_id: domainId
            })
        });

        if (!response.ok) {
            return 0;
        }

        const data = await response.json();
        
        if (data["message"] !== "success") {
            return 0;
        }

        return 1;

    } catch (error) {
        console.error('Error selecting domain', error);
        return 0;
    }
}