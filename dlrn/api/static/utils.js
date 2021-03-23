function timestampToString (timestamp) {
  const dt = parseInt(timestamp) * 1000
  const myDate = new Date(dt)
  return myDate.toLocaleString('en-GB')
}

function getVersionFromArtifacts (artifact) {
  if (artifact == null) {
    return ''
  }
  const list = artifact.split(',')
  const srcrpm = list.find(element => element.match('.src.rpm'))
  const pkgname = srcrpm.split('/').slice(-1)[0]
  const nvr = pkgname.match(/-(\d+|\.)+/)
  if (nvr != null) {
    return nvr[0].replace('-', '')
  } else {
    return ''
  }
}

function getReleaseFromArtifacts (artifact) {
  if (artifact == null) {
    return ''
  }
  const regexp = /\d+\.[0-9]{14}.[0-9a-f]{7}\.\w+/g
  const list = artifact.split(',')
  const srcrpm = list.find(element => element.match('.src.rpm'))
  const pkgname = srcrpm.split('/').slice(-1)[0]
  const value = pkgname.match(regexp)
  if (value != null) {
    return value[0]
  } else {
    return ''
  }
}

// This is a straight port to javascript of the funcion from
// dlrn/db.py
function getShardedCommitDir (commitHash, distroHash, extendedHash, component) {
  let distroHashSuffix = ''
  let componentPrefix = ''
  let extHashSuffix = ''

  if (distroHash != null) {
    distroHashSuffix = '_' + distroHash.slice(0, 8)
  }
  if (extendedHash != null) {
    if (extendedHash.length < 49) {
      extHashSuffix = '_' + extendedHash.slice(0, 8)
    } else {
      extHashSuffix = '_' + extendedHash.slice(0, 8) + '_' + extendedHash.slice(41, 49)
    }
  } else {
    extHashSuffix = ''
  }
  if (component != null) {
    componentPrefix = 'component/' + component + '/'
  } else {
    componentPrefix = ''
  }

  const output = componentPrefix + commitHash.slice(0, 2) + '/' + commitHash.slice(2, 4) + '/' + commitHash + distroHashSuffix + extHashSuffix
  return output
}

function generateNavigationButtons (url, name) {
  const urlParams = new URLSearchParams(window.location.search)
  const urlParams2 = new URLSearchParams(window.location.search)
  const offset = parseInt(urlParams.get('offset'))
  let prevOffset = 0
  let nextOffset = 0

  if (offset > 0) {
    prevOffset = offset - 100
  } else {
    prevOffset = 0
  }
  if (!isNaN(offset)) {
    nextOffset = offset + 100
  } else {
    nextOffset = 100
  }
  urlParams.set('offset', prevOffset)
  urlParams2.set('offset', nextOffset)
  $('#navigation1').html('<a href="' + url + '?' + urlParams + '" class="pf-c-button pf-m-control">Previous 100 ' + name + '</a><a href="' + url + '?' + urlParams2 + '" class="pf-c-button pf-m-control">Next 100 ' + name + '</a>')
}

function civotesHtml () {
  $('#dlrn').DataTable({
    paging: true,
    searching: false,
    order: [[2, 'desc']]
  })
  generateNavigationButtons('civotes.html', 'votes')
}

function civotesAggHtml () {
  $('#dlrn').DataTable({
    paging: true,
    searching: false,
    order: [[1, 'desc']]
  })
  generateNavigationButtons('civotes_agg.html', 'votes')
}

function reportHtml () {
  const urlParams = new URLSearchParams(window.location.search)
  let parameters = []
  const offset = parseInt(urlParams.get('offset'))
  const component = urlParams.get('component')
  const pkgname = urlParams.get('package')
  const success = urlParams.get('success')
  let commitquery = ''

  if (success != null) {
    if (success === '1') {
      parameters = parameters.concat(['status:"SUCCESS"'])
    } else {
      parameters = parameters.concat(['status:"FAILED"'])
    }
  }
  if (pkgname != null) {
    parameters = parameters.concat(['projectName:"' + pkgname + '"'])
  }
  if (component != null) {
    parameters = parameters.concat(['component:"' + component + '"'])
  }
  if (!isNaN(offset)) {
    parameters = parameters.concat(['offset:' + offset + ''])
  }

  if (parameters.length > 0) {
    commitquery = 'commits(' + parameters.join(',') + ')'
  } else {
    commitquery = 'commits'
  }

  $('#dlrn').DataTable({
    ajax: {
      url: 'graphql?query={ ' + commitquery + ' { dtBuild dtCommit projectName commitHash distroHash extendedHash component status artifacts} }',
      dataSrc: function (json) {
        return json.data.commits
      }
    },
    createdRow: function (row, data, dataIndex) {
      if (data.status !== 'SUCCESS') {
        $(row).addClass('failure')
      }
    },
    columns: [{
      data: 'dtBuild',
      render: {
        _: function (data, type, row, meta) {
          return timestampToString(data)
        },
        sort: function (data, type, row, meta) {
          return data
        }
      }
    },
    {
      data: 'dtCommit',
      render: {
        _: function (data, type, row, meta) {
          return timestampToString(data)
        },
        sort: function (data, type, row, meta) {
          return data
        }
      }
    },
    {
      data: 'projectName',
      render: function (data, type, row, meta) {
        return '<form action="report.html" method="get">' +
                                   '<input type="hidden" name="package" value="' + data + '" />' +
                                   '<button type="submit" class="pf-c-button"><i class="fa fa-link pull-left"></i>' +
                                   data + '</button></form>'
      }
    },
    {
      data: 'artifacts',
      render: function (data, type, row, meta) {
        return getVersionFromArtifacts(data)
      }
    },
    {
      data: 'artifacts',
      render: function (data, type, row, meta) {
        return getReleaseFromArtifacts(data)
      }
    },
    { data: 'commitHash' },
    {
      data: 'component',
      render: function (data, type, row, meta) {
        return '<form action="report.html" method="get"><input type="hidden" name="component" value="' +
                                   data +
                                   '" /><button type="submit" class="pf-c-button"><i class="fa fa-link pull-left"></i>' +
                                   data + '</button></form>'
      }
    },
    {
      data: 'status',
      render: function (data, type, row, meta) {
        if (data === 'SUCCESS') {
          return '<form action="report.html" method="get">' +
                                       '<input type="hidden" name="success" value=1 />' +
                                       '<button type="submit" class="pf-c-button"><i class="fas fa-link pull-left" style="color:#004153"></i>' +
                                       ' SUCCESS</button></form>'
        } else {
          return '<form action="report.html" method="get">' +
                                       '<input type="hidden" name="success" value=0 />' +
                                       '<button type="submit" class="pf-c-button"><i class="fas fa-link pull-left" style="color:red"></i>' +
                                       ' FAILED</button></form>'
        }
      }
    },
    {
      data: null,
      render: function (data, type, row, meta) {
        const commitDir = getShardedCommitDir(row.commitHash, row.distroHash, row.extendedHash, row.component)
        return '<a href="' + baseurl + '/' + commitDir + '">repo</a>'
      }
    },
    {
      data: null,
      render: function (data, type, row, meta) {
        const commitDir = getShardedCommitDir(row.commitHash, row.distroHash, row.extendedHash, row.component)
        return '<a href="' + baseurl + '/' + commitDir + '/rpmbuild.log">build log</a>'
      }
    }
    ],
    paging: true,
    searching: false,
    order: [[0, 'desc']]
  })
  generateNavigationButtons('report.html', 'commits')
}

function civotesDetailHtml () {
  const urlParams = new URLSearchParams(window.location.search)
  let parameters = []
  const offset = parseInt(urlParams.get('offset'))
  const component = urlParams.get('component')
  const success = urlParams.get('success')
  const ciname = urlParams.get('ci_name')
  let commitquery = ''

  if (commitId !== -1) {
    parameters = parameters.concat(['commitId: ' + commitId])
  }

  if (success != null) {
    if (success === 'True') {
      parameters = parameters.concat(['ciVote: true'])
    } else {
      parameters = parameters.concat(['ciVote: false'])
    }
  }
  if (component != null) {
    parameters = parameters.concat(['component:"' + component + '"'])
  }
  if (ciname != null) {
    parameters = parameters.concat(['ciName:"' + ciname + '"'])
  }
  if (!isNaN(offset)) {
    parameters = parameters.concat(['offset:' + offset + ''])
  }

  if (parameters.length > 0) {
    commitquery = 'civote(' + parameters.join(',') + ')'
  } else {
    commitquery = 'civote'
  }

  $('#dlrn').DataTable({
    ajax: {
      url: 'graphql?query={ ' + commitquery + ' { ciName commit { commitHash distroHash} component ciUrl ciVote ciInProgress timestamp notes} }',
      dataSrc: function (json) {
        return json.data.civote
      }
    },
    createdRow: function (row, data, dataIndex) {
      if (data.ciVote === false) {
        $(row).addClass('failure')
      }
    },
    columns: [{
      data: 'ciName',
      render: function (data, type, row, meta) {
        return '<form action="civotes_detail.html" method="get">' +
                           '<input type="hidden" name="ci_name" value="' + data + '" />' +
                           '<button type="submit" class="pf-c-button"><i class="fa fa-link pull-left"></i>' +
                           data + '</button></form>'
      }
    },
    {
      data: null,
      render: function (data, type, row, meta) {
        return '<form action="civotes_detail.html" method="get">' +
                           '<input type="hidden" name="commit_hash" value="' + row.commit.commitHash + '" />' +
                           '<input type="hidden" name="distro_hash" value="' + row.commit.distroHash + '" />' +
                           '<button type="submit" class="pf-c-button"><i class="fa fa-link pull-left"></i>' +
                           row.commit.commitHash + '_' + row.commit.distroHash.slice(0, 8) + '</button></form>'
      }
    },
    { data: 'component' },
    {
      data: 'ciUrl',
      render: function (data, type, row, meta) {
        return '<a href="' + data + '">link</a>'
      }
    },
    {
      data: 'ciVote',
      render: function (data, type, row, meta) {
        if (data === true) {
          return '<i class="fa pull-left" style="color:#004153">SUCCESS</i>'
        } else {
          return '<i class="fa pull-left" style="color:red">FAILED</i>'
        }
      }
    },
    {
      data: 'ciInProgress',
      render: function (data, type, row, meta) {
        if (data === true) {
          return '<i class="fa pull-left" style="color:red">IN PROGRESS</i>'
        } else {
          return '<i class="fa pull-left" style="color:#004153">FINISHED</i>'
        }
      }
    },
    {
      data: 'timestamp',
      render: {
        _: function (data, type, row, meta) {
          return timestampToString(data)
        },
        sort: function (data, type, row, meta) {
          return data
        }
      }
    },
    { data: 'notes' }
    ],
    paging: true,
    searching: false,
    order: [[6, 'desc']]
  })
  generateNavigationButtons('civotes_detail.html', 'votes')
}

function civotesAggDetailHtml () {
  const urlParams = new URLSearchParams(window.location.search)
  let parameters = []
  const offset = parseInt(urlParams.get('offset'))
  const refhash = urlParams.get('ref_hash')
  const success = urlParams.get('success')
  const ciname = urlParams.get('ci_name')
  let commitquery = ''

  if (success != null) {
    if (success === 'True') {
      parameters = parameters.concat(['ciVote: true'])
    } else {
      parameters = parameters.concat(['ciVote: false'])
    }
  }
  if (refhash != null) {
    parameters = parameters.concat(['refHash:"' + refhash + '"'])
  }
  if (ciname != null) {
    parameters = parameters.concat(['ciName:"' + ciname + '"'])
  }
  if (!isNaN(offset)) {
    parameters = parameters.concat(['offset:' + offset + ''])
  }

  if (parameters.length > 0) {
    commitquery = 'civoteAgg(' + parameters.join(',') + ')'
  } else {
    commitquery = 'civoteAgg'
  }

  $('#dlrn').DataTable({
    ajax: {
      url: 'graphql?query={ ' + commitquery + ' { ciName refHash ciUrl ciVote ciInProgress timestamp notes} }',
      dataSrc: function (json) {
        return json.data.civoteAgg
      }
    },
    createdRow: function (row, data, dataIndex) {
      if (data.ciVote === false) {
        $(row).addClass('failure')
      }
    },
    columns: [{
      data: 'ciName',
      render: function (data, type, row, meta) {
        return '<form action="civotes_agg_detail.html" method="get">' +
                           '<input type="hidden" name="ci_name" value="' + data + '" />' +
                           '<button type="submit" class="pf-c-button"><i class="fa fa-link pull-left"></i>' +
                           data + '</button></form>'
      }
    },
    {
      data: 'refHash',
      render: function (data, type, row, meta) {
        return '<form action="civotes_agg_detail.html" method="get">' +
                           '<input type="hidden" name="ref_hash" value="' + data + '" />' +
                           '<button type="submit" class="pf-c-button"><i class="fa fa-link pull-left"></i>' +
                           data + '</button></form>'
      }
    },
    {
      data: 'ciUrl',
      render: function (data, type, row, meta) {
        return '<a href="' + data + '">link</a>'
      }
    },
    {
      data: 'ciVote',
      render: function (data, type, row, meta) {
        if (data === true) {
          return '<i class="fa pull-left" style="color:#004153">SUCCESS</i>'
        } else {
          return '<i class="fa pull-left" style="color:red">FAILED</i>'
        }
      }
    },
    {
      data: 'ciInProgress',
      render: function (data, type, row, meta) {
        if (data === true) {
          return '<i class="fa pull-left" style="color:red">IN PROGRESS</i>'
        } else {
          return '<i class="fa pull-left" style="color:#004153">FINISHED</i>'
        }
      }
    },
    {
      data: 'timestamp',
      render: {
        _: function (data, type, row, meta) {
          return timestampToString(data)
        },
        sort: function (data, type, row, meta) {
          return data
        }
      }
    },
    { data: 'notes' }
    ],
    paging: true,
    searching: false,
    order: [[5, 'desc']]
  })
  generateNavigationButtons('civotes_agg_detail.html', 'votes')
}
